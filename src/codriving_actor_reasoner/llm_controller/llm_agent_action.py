from .prompt_llm import *
from .Scenario_description import Scenario
import json
from openai import OpenAI
import numpy as np
import gym
import re
import os

api_key = os.getenv("OPENAI_API_KEY", "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")

class LlmAgent_action_module():
    def __init__(self, env):
        self.sce = Scenario(env.road, vehicleCount=10)
        self.frame = 0
        self.done = False
        self.toolModels = [
            getAvailableActions(),
            getAvailableLanes(self.sce),
            getLaneInvolvedCar(self.sce),
            isChangeLaneConflictWithCar(self.sce),
            isAccelerationConflictWithCar(self.sce),
            isKeepSpeedConflictWithCar(self.sce),
            isDecelerationSafe(self.sce),
        ]
        self.pre_prompt = PRE_DEF_PROMPT()
        self.get_actions(env)
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        if provider == "ollama":
            self.client = OpenAI(
                api_key=os.getenv("LLM_API_KEY", "ollama"),
                base_url=os.getenv("LLM_API_BASE", "http://127.0.0.1:11434/v1")
            )
            self.model_name = os.getenv("LLM_MODEL", "qwen2.5:7b")
        else:
            self.client = OpenAI(
                api_key=os.getenv("LLM_API_KEY", api_key),
                base_url=os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
            )
            self.model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def llm_controller_run(self, env, negotiation_prompt, conflicting_info, controlled_vehicles, memory):
        llm_actions = []
        for i, ego_veh in enumerate(controlled_vehicles):
            scene_name = self.get_scene_name(env)
            if scene_name == 'intersection':
                speed_limit = 5
            else:
                speed_limit = 20
            ego_veh.speed = speed_limit if ego_veh.speed > speed_limit else ego_veh.speed
            negotiation_results = self.transfer_negotiation_prompts_to_results(ego_veh, negotiation_prompt)
            prompt_info = self.prompt_engineer(ego_veh, env.road, env, negotiation_results, conflicting_info)
            action_val = self.send_to_chatgpt(ego_veh, prompt_info, negotiation_results, memory)
            self.memory_update(memory, prompt_info, action_val)
            llm_actions.append(action_val[0])
            print("llm_action:", action_val[0], ego_veh, 'speed now:', ego_veh.speed)
        return llm_actions

    def get_scene_name(self, env):
        scene_name = env.spec.id
        match = re.search(r'(merge|intersection|highway)', scene_name)
        simplified_scene_name = match.group(0) if match else 'unknown'
        return simplified_scene_name

    def get_actions(self, env):
        scene_name = self.get_scene_name(env)
        if scene_name == 'highway':
            self.ACTIONS_ALL = {
                0: 'LANE_LEFT',
                1: 'IDLE',
                2: 'LANE_RIGHT',
                3: 'FASTER',
                4: 'SLOWER'
            }
            self.is_intersection = False
        elif scene_name == 'merge' or scene_name == 'intersection':
            self.ACTIONS_ALL = {
                1: 'IDLE',
                3: 'FASTER',
                4: 'SLOWER',
            }
            self.is_intersection = True
        else:
            self.ACTIONS_ALL = None

    def get_action_id_from_name(self, action_name, actions_all):
        for id, name in actions_all.items():
            if name == action_name or name == action_name.upper():
                return id
        if action_name:
            upper_name = action_name.upper()
            if 'FAST' in upper_name or 'FST' in upper_name: return 3
            if 'SLOW' in upper_name or 'SLW' in upper_name: return 4
            if 'IDLE' in upper_name or 'IDL' in upper_name: return 1
            if 'LEFT' in upper_name: return 0
            if 'RIGHT' in upper_name: return 2
        return 1

    def transfer_negotiation_prompts_to_results(self, ego_veh, negotiation_prompt):
        vehicle_conflicts = self.extract_vehicle_conflicts(negotiation_prompt, str(ego_veh).split(":")[0].strip())
        negotiation_results = ""
        for conflict in vehicle_conflicts:
            first_vehicle, second_vehicle, order = conflict
            if first_vehicle == str(ego_veh).split(":")[0].strip():
                negotiation_results += f"- You have conflict with {second_vehicle}. It is suggested that you should {'passes first' if order == 'first' else 'passes second'}.\n"
            else:
                negotiation_results += f"- You have conflict with {first_vehicle}. It is suggested that you should {'passes first' if order == 'first' else 'passes second'}.\n"
        return negotiation_results

    def relative_memory(self, memory, prompt_info, style='normal'):
        if memory is None:
            return ""
        experience = ""
        extract_prompt = prompt_info.strip().split('\n')
        query_scenario = '\n'.join(extract_prompt[-2:])
        # Append style to query_scenario so retrieveMemory can determine the partition!
        query_scenario += f"\nInteraction vehicle driving style: {style}"
        past_decisions = memory.retrieveMemory(query_scenario, top_k=2)
        for past_decision in past_decisions:
            experience += f"- Last time {past_decision['negotiation_result']}, you choose to {past_decision['final_action']}, it is {past_decision['comments']}\n"
        experience += f"Above messages are some examples of how you make a decision in the past. Those scenarios are similar to the current scenario. You should refer to those examples to make a decision for the current scenario."
        return experience

    def memory_update(self, memory, prompt_info, action_val):
        # action_val is [llm_action, style, intention]
        if memory is None:
            return
        llm_action_id = action_val[0][0]
        llm_action_name = self.ACTIONS_ALL.get(llm_action_id, "IDLE")
        style = action_val[1]
        intention = action_val[2]
        
        human_question = str(None)
        negotiation = str(None)
        action = str(llm_action_name)
        
        saved_info = prompt_info.strip().split('\n')[-1]
        if saved_info != ' Conflict info is empty':
            relation = re.findall(r'_(.*?)_', saved_info)
            if len(relation) > 0:
                comments = generate_comment(relation[0], llm_action_id)
            else:
                comments = 'recommended to FASTER'
            print(relation[0] if len(relation) > 0 else 'no relation', llm_action_id, comments)
        else:
            comments = 'recommended to FASTER'
            
        # Append style and intention to prompt_info so determine_memory_type in memory.py can read it
        sce_descrip = prompt_info + f"\nInteraction vehicle driving style: {style}\nInteraction vehicle intention: {intention}"
        memory.addMemory(sce_descrip, human_question, negotiation, action, comments)
        print(f' New memory has been added into style partition: {style} ...')

    def send_to_chatgpt(self, ego_veh, current_scenario, negotiation_results, memory):
        client = self.client
        model_name = self.model_name

        if self.is_intersection:
            message_prefix = self.pre_prompt.SYSTEM_MESSAGE_PREFIX_intersection
            traffic_rules = self.pre_prompt.get_traffic_rules(self.is_intersection)
            decision_cautions = self.pre_prompt.get_decision_cautions(self.is_intersection)
            actions_list = "IDLE, FASTER, SLOWER"
        else:
            message_prefix = self.pre_prompt.SYSTEM_MESSAGE_PREFIX
            traffic_rules = self.pre_prompt.get_traffic_rules()
            decision_cautions = self.pre_prompt.get_decision_cautions()
            actions_list = "LANE_LEFT, IDLE, LANE_RIGHT, FASTER, SLOWER"

        style_latest = getattr(ego_veh, "estimated_style", "normal")
        past_memory = self.relative_memory(memory, current_scenario, style=style_latest)

        prompt = (f"{message_prefix}"
                  f"You, the 'ego' car, are now driving. You have already driven for some seconds.\n"
                  "Here is the current scenario:\n"
                  f"{current_scenario}\n\n"
                  "There are several rules you need to follow when you drive:\n"
                  f"{traffic_rules}\n\n"
                  "Here are your attention points:\n"
                  f"{decision_cautions}\n\n"
                  "Here is your action when scenarios are similar to the current scenario in the past, you should learn from past memory try not to take the cation that cause more danger:\n"
                  f"{past_memory}\n\n"
                  "Based on the planning trajectory, you have the following conflicts with other vehicles.\n"
                  "Here are the conflicts and the suggested passing orders (when you are suggested to passes second, better to slow down): \n"
                  f"{negotiation_results}\n\n"
                  "You need to consider the following questions step by step to reach your conclusion:\n"
                  "1. What is the likely intention of the surrounding vehicles? (ACCELERATE or DECELERATE)\n"
                  "2. What is the driving style of the surrounding vehicles? (AGGRESSIVE or CONSERVATIVE)\n"
                  "3. What action should you take next? Your action should be one of the available actions.\n\n"
                  "Once you make a final decision, output it in the following format (ONLY OUTPUT THE JSON AND NOTHING ELSE):\n"
                  "```\n"
                  "Final Answer: \n"
                  "    \"surrounding vehicle intention\": {\"<surrounding vehicle's intention, only output ACCELERATE or DECELERATE)>\"},\n"
                  "    \"style\": {\"<surrounding vehicle's driving style, only output AGGRESSIVE or CONSERVATIVE)>\"},\n"
                  "    \"decision\": {\"<ego car's decision, ONE of the available actions (decision have to be one of the following action: " + actions_list + ")>\"}\n"
                  "```\n")

        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": prompt},])

        llm_response = completion.choices[0].message
        decision_content = llm_response.content
        llm_suggested_action, style, intention = self.extract_output(decision_content)
        print(f"llm action: {llm_suggested_action}, style: {style}, intention: {intention}")

        llm_action_id = self.get_action_id_from_name(llm_suggested_action, self.ACTIONS_ALL)
        llm_action = np.array([llm_action_id])
        return [llm_action, style, intention]

    def extract_output(self, response_content):
        try:
            start_decision = response_content.find('"decision": {') + len('"decision": {')
            end_decision = response_content.find('}', start_decision)
            decision = response_content[start_decision:end_decision].strip().strip('"')

            start_style = response_content.find('"style": {') + len('"style": {')
            end_style = response_content.find('}', start_style)
            style = response_content[start_style:end_style].strip().strip('"')

            start_intention = response_content.find('"surrounding vehicle intention": {') + len('"surrounding vehicle intention": {')
            end_intention = response_content.find('}', start_intention)
            intention = response_content[start_intention:end_intention].strip().strip('"')

            # Clean decision
            if self.is_intersection:
                if "FASTER" in decision.upper():
                    decision = "FASTER"
                elif "SLOWER" in decision.upper():
                    decision = "SLOWER"
                elif "IDLE" in decision.upper():
                    decision = "IDLE"
            else:
                if "LANE_LEFT" in decision.upper():
                    decision = "LANE_LEFT"
                elif "LANE_RIGHT" in decision.upper():
                    decision = "LANE_RIGHT"
                elif "FASTER" in decision.upper():
                    decision = "FASTER"
                elif "SLOWER" in decision.upper():
                    decision = "SLOWER"
                elif "IDLE" in decision.upper():
                    decision = "IDLE"
                    
            if style.upper() not in ["CONSERVATIVE", "AGGRESSIVE"]:
                style = "normal"
            else:
                style = style.lower()
                
            if intention.upper() not in ["ACCELERATE", "DECELERATE"]:
                intention = "GENERAL"
            else:
                intention = intention.upper()

            return decision, style, intention
        except Exception as e:
            print(f"Error when extracting output: {e}. Fallback to IDLE, normal, GENERAL")
            return "IDLE", "normal", "GENERAL"

    def extract_decision(self, response_content):
        # Kept for compatibility if called from elsewhere
        dec, _, _ = self.extract_output(response_content)
        return dec

    def prompt_engineer(self,  ego_veh, road, env, negotiation_results, conflicting_info):
        msg0 = available_action(self.toolModels, ego_veh, road, env)
        availabel_lane, msg1 = get_available_lanes(self.toolModels, ego_veh, road, env)
        msg2, lane_cars_id = get_involved_cars(self.toolModels, ego_veh, road, env, availabel_lane)

        if availabel_lane["leftLane"] != "" or availabel_lane["rightLane"] != "":
            safety_assessment = assess_lane_change_safety(self.toolModels, lane_cars_id, availabel_lane, ego_veh)
        else:
            safety_assessment = "There is no need to assess lane change safety."
        safety_msg = check_safety_in_current_lane(self.toolModels, lane_cars_id, availabel_lane, ego_veh, env)
        safety_msg2, most_dangerous_info = check_safety_with_conflict_vehicles(ego_veh, negotiation_results, conflicting_info, env)
        prompt_info = format_training_info(msg0, msg1, msg2, availabel_lane, lane_cars_id, safety_assessment, safety_msg, safety_msg2, most_dangerous_info)
        return prompt_info

    def extract_vehicle_conflicts(self, prompt: str, vehicle_id: str) -> list:
        pattern = re.compile(r'"first_vehicle": "(MDPVehicle #[0-9]+|IDMVehicle #[0-9]+)", "second_vehicle": "(MDPVehicle #[0-9]+|IDMVehicle #[0-9]+)"')
        conflicts = pattern.findall(prompt)

        vehicle_conflicts = []
        for first, second in conflicts:
            if first == vehicle_id:
                vehicle_conflicts.append((first, second, 'first'))
            elif second == vehicle_id:
                vehicle_conflicts.append((first, second, 'second'))
        return vehicle_conflicts

    def reset(self, **kwargs):
        obs = self.env.reset(**kwargs)
        return obs

    def get_available_actions(self):
        if hasattr(self.env, 'get_available_actions'):
            return self.env.get_available_actions()
        else:
            raise NotImplementedError(
                "The method get_available_actions is not implemented in the underlying environment.")
