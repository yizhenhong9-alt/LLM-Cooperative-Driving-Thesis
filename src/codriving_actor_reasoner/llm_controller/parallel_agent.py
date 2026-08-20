import os
import time
import threading
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from .llm_agent_action import LlmAgent_action_module
from .llm_agent_negotiation_system import LlmAgent_negotiation_module

# Action map for highway-env action spaces
ACTIONS_ALL = {
    "LANE_LEFT": 0,
    "IDLE": 1,
    "LANE_RIGHT": 2,
    "FASTER": 3,
    "SLOWER": 4
}

def clean_action_str(action_val):
    if isinstance(action_val, np.ndarray):
        if len(action_val) > 0:
            action_id = int(action_val[0])
            for k, v in ACTIONS_ALL.items():
                if v == action_id:
                    return k
        return "IDLE"
    elif isinstance(action_val, str):
        action_val = action_val.strip()
        if action_val.startswith("[") and action_val.endswith("]"):
            try:
                action_id = int(action_val[1:-1].strip())
                for k, v in ACTIONS_ALL.items():
                    if v == action_id:
                        return k
            except Exception:
                pass
        if action_val.isdigit():
            action_id = int(action_val)
            for k, v in ACTIONS_ALL.items():
                if v == action_id:
                    return k
        if action_val in ACTIONS_ALL:
            return action_val
    return "IDLE"

class ParallelAgentCoordination:
    def __init__(self, env, memory):
        self.negotiator = LlmAgent_negotiation_module(env)
        self.action_module = LlmAgent_action_module(env)
        self.memory = memory
        self.is_training = True
        
        # Shared memory thread-safe parameters
        self.shared_negotiation_prompt = ""
        self.shared_conflicting_info = ""
        self.shared_reasoner_actions = {}  # maps vehicle ID to latest recommended action string
        self.shared_reasoner_styles = {}   # maps vehicle ID to latest estimated driving style
        
        self.stop_threads = False
        # Main background executor for the Reasoner loop thread
        self.reasoner_thread_executor = ThreadPoolExecutor(max_workers=1)
        # Parallel executor for simultaneous LLM API calls for multiple CAVs
        self.api_executor = ThreadPoolExecutor(max_workers=10)
        self.lock = threading.Lock()
        
    def start_reasoner(self, env):
        self.stop_threads = False
        self.reasoner_thread_executor.submit(self.reasoner_loop, env)
        print("========== Reasoner Thread Started (1Hz Background loop) ==========")
        
    def stop_reasoner(self):
        self.stop_threads = True
        self.reasoner_thread_executor.shutdown(wait=False)
        self.api_executor.shutdown(wait=False)
        print("========== Reasoner Thread Stopped ==========")

    def reasoner_loop(self, env):
        """Asynchronous Reasoner loop running at 1Hz in the background"""
        while not self.stop_threads:
            try:
                # 1. Run V2X conflict detection & priority scheduling
                negotiation_prompt, conflicting_info = self.negotiator.llm_controller_run(env)
                
                with self.lock:
                    self.shared_negotiation_prompt = negotiation_prompt
                    self.shared_conflicting_info = conflicting_info
                
                controlled_vehs = list(env.controlled_vehicles)
                
                # 2. Concurrently query LLM actions and style estimators for all CAVs
                def process_single_cav(ego_veh):
                    if self.stop_threads:
                        return
                    try:
                        scene_name = self.action_module.get_scene_name(env)
                        speed_limit = 5 if scene_name == 'intersection' else 20
                        ego_veh.speed = speed_limit if ego_veh.speed > speed_limit else ego_veh.speed
                        
                        negotiation_results = self.action_module.transfer_negotiation_prompts_to_results(ego_veh, negotiation_prompt)
                        prompt_info = self.action_module.prompt_engineer(ego_veh, env.road, env, negotiation_results, conflicting_info)
                        
                        # Call API (returns [llm_action_id_arr, style, intention])
                        action_val = self.action_module.send_to_chatgpt(ego_veh, prompt_info, negotiation_results, self.memory)
                        
                        # Store style estimation directly on the vehicle object for relative memory queries
                        ego_veh.estimated_style = action_val[1]
                        ego_veh.estimated_intention = action_val[2]
                        
                        # Update database memory
                        if self.is_training:
                            self.action_module.memory_update(self.memory, prompt_info, action_val)
                        
                        with self.lock:
                            self.shared_reasoner_actions[id(ego_veh)] = action_val[0]
                            self.shared_reasoner_styles[id(ego_veh)] = action_val[1]
                    except Exception as e:
                        print(f"Error in parallel reasoning for vehicle {id(ego_veh)}: {e}")

                # Submit all queries concurrently to the thread pool
                futures = [self.api_executor.submit(process_single_cav, v) for v in controlled_vehs]
                
                # Wait for all parallel API requests to finish
                for fut in futures:
                    fut.result()
                    
            except RuntimeError as e:
                # If we are shutting down the simulation, cannot schedule new futures is expected and can be ignored
                if not self.stop_threads:
                    print(f"Warning: Reasoner loop encountered a runtime error: {e}")
            except Exception as e:
                print(f"Warning: Reasoner loop encountered an exception: {e}")
            
            # Sleep 1.0s to simulate 1Hz loop frequency
            time.sleep(1.0)

    def get_actor_actions(self, env, memory):
        """High-frequency Actor loop running at >40Hz in the main thread"""
        actor_actions = []
        controlled_vehs = list(env.controlled_vehicles)
        
        with self.lock:
            negotiation_prompt = self.shared_negotiation_prompt
            conflicting_info = self.shared_conflicting_info
            reasoner_actions = self.shared_reasoner_actions.copy()
            reasoner_styles = self.shared_reasoner_styles.copy()
            
        for veh in controlled_vehs:
            scene_name = self.action_module.get_scene_name(env)
            speed_limit = 5 if scene_name == 'intersection' else 20
            veh.speed = speed_limit if veh.speed > speed_limit else veh.speed
            
            negotiation_results = self.action_module.transfer_negotiation_prompts_to_results(veh, negotiation_prompt)
            prompt_info = self.action_module.prompt_engineer(veh, env.road, env, negotiation_results, conflicting_info)
            
            # 1. Fast Memory Retrieval from style partition using NumPy RAM cache
            style = reasoner_styles.get(id(veh), 'normal')
            query_scenario = prompt_info + f"\nInteraction vehicle driving style: {style}"
            
            retrieved_mem = memory.retrieveMemory_fast(query_scenario, top_k=1)
            
            veh_display_id = getattr(veh, 'id', id(veh))
            if retrieved_mem and len(retrieved_mem) > 0:
                raw_action = retrieved_mem[0]['final_action']
                action_str = clean_action_str(raw_action)
                print(f"[Actor Fast Retrieve] CAV {veh_display_id} retrieved action: {action_str} (raw: {raw_action}) [Style Partition: {style}]")
            else:
                raw_action = reasoner_actions.get(id(veh), "IDLE")
                action_str = clean_action_str(raw_action)
                print(f"[Actor Fallback] CAV {veh_display_id} using Reasoner action: {action_str} (raw: {raw_action})")
                
            # 2. Refined Geometric Safety Shield (Frenet heading-projection check)
            # Adjust safety margin depending on whether the estimated style is aggressive
            safety_margin = 8.0 if style.lower() == 'aggressive' else 5.0
            
            is_unsafe = False
            heading_vec = np.array([np.cos(veh.heading), np.sin(veh.heading)])
            
            for other in env.road.vehicles:
                if id(other) != id(veh):
                    vec = other.position - veh.position
                    dist = np.linalg.norm(vec)
                    
                    if dist < safety_margin:
                        # Project onto heading vector to find longitudinal and lateral distances
                        long_dist = np.dot(vec, heading_vec)
                        lat_dist = np.linalg.norm(vec - long_dist * heading_vec)
                        
                        # Case A: Vehicle is directly ahead of us in the same or overlapping lane
                        if long_dist > 0 and lat_dist < 2.0:
                            rel_speed = veh.speed - other.speed
                            if rel_speed > 0 and action_str in ["FASTER", "IDLE"]:
                                is_unsafe = True
                                break
                                
                        # Case B: Vehicle is in the adjacent lane and we are attempting to change lanes
                        if action_str in ["LANE_LEFT", "LANE_RIGHT"]:
                            if lat_dist < 4.0 and abs(long_dist) < 8.0:
                                is_unsafe = True
                                break
            
            if is_unsafe:
                print(f"[Safety Shield ACTIVE] CAV {veh_display_id} action overridden from {action_str} to SLOWER (Safety Margin: {safety_margin}m, style: {style})")
                action_str = "SLOWER"
                
            action_id = ACTIONS_ALL.get(action_str, 1)
            actor_actions.append([action_id])
            
        return actor_actions
