"""
Generate CSV with 175 teams for testing
Run: python generate_teams_csv.py
Output: teams_175.csv
"""

def generate_teams_csv(num_teams=175, output_file="teams_175.csv"):
    """Generate CSV with sample team data"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write('team_name,leader_name,leader_phone,member_2,member_3,member_4,college\n')
        
        # Generate teams
        for i in range(1, num_teams + 1):
            team_name = f"Team {i:03d}"
            leader_name = f"Leader {i:03d}"
            leader_phone = str(9876543210 + i)
            member_2 = f"Member A{i:03d}"
            member_3 = f"Member B{i:03d}"
            member_4 = f"Member C{i:03d}" if i % 2 == 0 else ""  # Some teams have 3 members
            college = f"College {(i % 20) + 1}"  # 20 different colleges
            
            f.write(f"{team_name},{leader_name},{leader_phone},{member_2},{member_3},{member_4},{college}\n")
    
    print(f"✓ Generated {num_teams} teams in {output_file}")
    print(f"\nFirst 3 rows:")
    with open(output_file, 'r') as f:
        for i, line in enumerate(f):
            if i < 4:  # Header + 3 data rows
                print(f"  {line.strip()}")
    
    print(f"\nLast 3 rows:")
    with open(output_file, 'r') as f:
        lines = f.readlines()
        for line in lines[-3:]:
            print(f"  {line.strip()}")
    
    print(f"\n{'='*60}")
    print("Upload this file via Admin Dashboard:")
    print("  http://localhost:3000/admin-dashboard.html")
    print("  → Upload Teams (CSV) section")
    print("  → Select file → Click 'Upload Teams'")
    print(f"{'='*60}")


def generate_with_real_names(num_teams=175, output_file="teams_175_realistic.csv"):
    """Generate CSV with more realistic names"""
    first_names = ["John", "Jane", "Alice", "Bob", "Charlie", "Diana", "Emma", "Frank", 
                   "Grace", "Henry", "Iris", "Jack", "Kate", "Leo", "Maya", "Noah",
                   "Olivia", "Peter", "Quinn", "Rachel", "Sam", "Tina", "Uma", "Victor"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
                  "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
                  "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    colleges = ["MIT", "Stanford", "Harvard", "Berkeley", "CMU", "Caltech", "Princeton",
                "Yale", "Columbia", "Cornell", "UPenn", "Northwestern", "Duke", "Chicago",
                "Brown", "Dartmouth", "Rice", "Vanderbilt", "Emory", "Notre Dame"]
    
    import random
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('team_name,leader_name,leader_phone,member_2,member_3,member_4,college\n')
        
        for i in range(1, num_teams + 1):
            team_name = f"Team {random.choice(['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta', 'Iota', 'Kappa'])}{i:03d}"
            
            # Generate unique names
            leader = f"{random.choice(first_names)} {random.choice(last_names)}"
            member2 = f"{random.choice(first_names)} {random.choice(last_names)}"
            member3 = f"{random.choice(first_names)} {random.choice(last_names)}"
            member4 = f"{random.choice(first_names)} {random.choice(last_names)}" if i % 3 != 0 else ""
            
            phone = str(9876543210 + i)
            college = random.choice(colleges)
            
            f.write(f"{team_name},{leader},{phone},{member2},{member3},{member4},{college}\n")
    
    print(f"✓ Generated {num_teams} teams with realistic names in {output_file}")


if __name__ == "__main__":
    import sys
    
    print("Team CSV Generator")
    print("=" * 60)
    
    mode = input("Choose mode:\n  1. Simple names (Team 001, Leader 001, etc.)\n  2. Realistic names\n  Enter choice (1/2): ").strip()
    
    if mode == "2":
        generate_with_real_names()
    else:
        generate_teams_csv()
    
    print("\n✓ Done! File is ready to upload.")
