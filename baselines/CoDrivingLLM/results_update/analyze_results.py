import os
import glob
import pandas as pd
import numpy as np

# Configuration parameters
COLLISION_THRESHOLD = 3.0  # distance threshold in meters for collision
INTERSECTION_CENTER_X = 0.0
INTERSECTION_CENTER_Y = 0.0
INTERSECTION_RADIUS = 8.0  # conflict zone radius in meters

def analyze_folder(folder_path):
    excel_path = os.path.join(folder_path, "excel", "*.xlsx")
    files = glob.glob(excel_path)
    
    if not files:
        # Check if the excel subfolder is directly in the path
        excel_path = os.path.join(folder_path, "*.xlsx")
        files = glob.glob(excel_path)
        
    if not files:
        print(f"Warning: No Excel files found in {folder_path}")
        return None
        
    print(f"Analyzing {len(files)} rounds in: {folder_path}...")
    
    successful_rounds = 0
    total_rounds = len(files)
    all_speeds = []
    min_speeds = []
    max_speeds = []
    all_pets = []
    
    for file in files:
        xls = pd.ExcelFile(file)
        sheets = xls.sheet_names
        
        # Load all vehicle data for this episode
        veh_data = {}
        for sheet in sheets:
            if sheet.lower() == 'sheet':
                continue
            df = pd.read_excel(file, sheet_name=sheet)
            if 't' not in df.columns:
                continue
            veh_data[sheet] = df
            
        # 1. Collision check for the episode
        # Find the maximum time step 't' in this episode
        max_t = 0
        for sheet, df in veh_data.items():
            if 't' in df.columns and len(df) > 0:
                max_t = max(max_t, df['t'].max())
                
        is_collision = False
        
        # Check distance between all pairs of vehicles at each time step 't'
        for t in range(int(max_t) + 1):
            active_vehs = []
            for sheet, df in veh_data.items():
                row = df[df['t'] == t]
                if not row.empty:
                    # row values: x, y, v, theta, background_veh?
                    x = row.iloc[0]['x']
                    y = row.iloc[0]['y']
                    v = row.iloc[0]['v']
                    is_bg = row.iloc[0]['background_veh?']
                    active_vehs.append((sheet, x, y, v, is_bg))
            
            # Compare distances between all pairs
            for idx1 in range(len(active_vehs)):
                for idx2 in range(idx1 + 1, len(active_vehs)):
                    name1, x1, y1, v1, bg1 = active_vehs[idx1]
                    name2, x2, y2, v2, bg2 = active_vehs[idx2]
                    
                    dist = np.sqrt((x1 - x2)**2 + (y1 - y2)**2)
                    if dist < COLLISION_THRESHOLD:
                        is_collision = True
                        break
                if is_collision:
                    break
            if is_collision:
                break
                
        if not is_collision:
            successful_rounds += 1
            
            # 2. Gather speeds of controlled vehicles (non-background) in successful rounds
            for sheet, df in veh_data.items():
                if len(df) > 0:
                    # filter out background vehicles if the column exists
                    if 'background_veh?' in df.columns:
                        controlled_df = df[df['background_veh?'] == True]
                    else:
                        controlled_df = df
                        
                    if not controlled_df.empty:
                        speeds = controlled_df['v'].tolist()
                        all_speeds.extend(speeds)
                        min_speeds.append(min(speeds))
                        max_speeds.append(max(speeds))
            
            # 3. Calculate Post-Encroachment Time (PET) in successful rounds
            # Track when each vehicle enters and exits the conflict zone (intersection center)
            conflict_intervals = []
            for name, df in veh_data.items():
                in_conflict = False
                entry_t = None
                exit_t = None
                
                for _, row in df.iterrows():
                    x = row['x']
                    y = row['y']
                    curr_t = row['t']
                    
                    dist_to_center = np.sqrt((x - INTERSECTION_CENTER_X)**2 + (y - INTERSECTION_CENTER_Y)**2)
                    if dist_to_center < INTERSECTION_RADIUS:
                        if not in_conflict:
                            in_conflict = True
                            entry_t = curr_t
                    else:
                        if in_conflict:
                            in_conflict = False
                            exit_t = curr_t
                            conflict_intervals.append((name, entry_t, exit_t))
                            entry_t = None
                            exit_t = None
                            
                # If still in conflict at the end of the episode
                if in_conflict and entry_t is not None:
                    conflict_intervals.append((name, entry_t, max_t))
            
            # Calculate PET between all pairs that crossed the conflict zone
            # PET is the time gap between A exiting and B entering
            for idx1 in range(len(conflict_intervals)):
                for idx2 in range(idx1 + 1, len(conflict_intervals)):
                    name1, entry1, exit1 = conflict_intervals[idx1]
                    name2, entry2, exit2 = conflict_intervals[idx2]
                    
                    if name1 == name2:
                        continue
                        
                    # Determine who entered first
                    if entry1 < entry2:
                        # Vehicle 1 entered first
                        pet = entry2 - exit1
                    else:
                        # Vehicle 2 entered first
                        pet = entry1 - exit2
                        
                    # Only count positive PETs (non-overlapping)
                    if pet > 0:
                        all_pets.append(pet)

    success_rate = (successful_rounds / total_rounds) * 100.0 if total_rounds > 0 else 0
    avg_speed = np.mean(all_speeds) if all_speeds else 0
    min_speed = np.mean(min_speeds) if min_speeds else 0
    max_speed = np.mean(max_speeds) if max_speeds else 0
    avg_pet = np.mean(all_pets) if all_pets else float('nan')
    min_pet = np.min(all_pets) if all_pets else float('nan')
    
    return {
        "success_rate": success_rate,
        "avg_speed": avg_speed,
        "min_speed": min_speed,
        "max_speed": max_speed,
        "avg_pet": avg_pet,
        "min_pet": min_pet,
        "total_rounds": total_rounds,
        "successful_rounds": successful_rounds
    }

def main():
    # Identify available results folders
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # We will look for standard folders
    folders_to_compare = {
        "Intersection (No Memory)": os.path.join(base_dir, "intersection_no_memory"),
        "Intersection (With Memory)": os.path.join(base_dir, "intersection_with_memory"),
        "Merge (No Memory)": os.path.join(base_dir, "merge_no_memory"),
        "Merge (With Memory)": os.path.join(base_dir, "merge_with_memory"),
        "Highway (No Memory)": os.path.join(base_dir, "highway_no_memory"),
        "Highway (With Memory)": os.path.join(base_dir, "highway_with_memory")
    }
    
    results = {}
    for name, path in folders_to_compare.items():
        if os.path.exists(path):
            res = analyze_folder(path)
            if res:
                results[name] = res
                
    if not results:
        print("No folders found to analyze. Please place this script next to your results folders.")
        return
        
    # Print the report
    print("\n" + "="*80)
    print("                      COOPERATIVE DRIVING SIMULATION REPORT")
    print("="*80)
    print(f"{'Experiment Combination':<30} | {'Success%':<10} | {'Avg Speed':<10} | {'Avg PET':<10} | {'Min PET':<10}")
    print("-"*80)
    
    for name, res in results.items():
        pet_str = f"{res['avg_pet']:.2f}s" if not np.isnan(res['avg_pet']) else "N/A"
        min_pet_str = f"{res['min_pet']:.2f}s" if not np.isnan(res['min_pet']) else "N/A"
        print(f"{name:<30} | {res['success_rate']:.1f}% | {res['avg_speed']:.2f} m/s | {pet_str:<10} | {min_pet_str:<10}")
    print("="*80)
    print("Note: PET = Post-Encroachment Time. Min PET should ideally be > 1.5s for safety.")
    print("="*80)

if __name__ == "__main__":
    main()
