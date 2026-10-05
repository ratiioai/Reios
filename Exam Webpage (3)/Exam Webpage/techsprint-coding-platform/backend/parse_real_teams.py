"""
Parse the real registration CSV and create teams_real.csv
"""
import csv
import re

import os
# Read the uploaded CSV data
input_file = "SPEC INDUSTRY HACK (Responses) - Form Responses 1.csv"
if not os.path.exists(input_file) and os.path.exists(os.path.join("..", input_file)):
    input_file = os.path.join("..", input_file)
output_file = "teams_real.csv"

def clean_phone(phone):
    """Clean phone number - remove spaces, +91, etc."""
    if not phone:
        return ""
    # Remove all non-digit characters
    phone = re.sub(r'[^\d]', '', str(phone))
    # Take last 10 digits
    if len(phone) > 10:
        phone = phone[-10:]
    return phone

def clean_name(name):
    """Clean name - remove extra spaces, quotes"""
    if not name:
        return ""
    return re.sub(r'\s+', ' ', str(name).strip().strip('"\''))

teams = []
team_id = 1

with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    for row in reader:
        team_name = clean_name(row.get('TEAM NAME', ''))
        leader_name = clean_name(row.get('TEAM LEADER NAME', ''))
        leader_phone = clean_phone(row.get('TEAM LEADER MOBILE NUMBER', ''))
        college = clean_name(row.get('TEAM LEADER COLLEGE NAME', ''))
        
        # Member details
        member1_name = clean_name(row.get('Team Member 1 Name', ''))
        member2_name = clean_name(row.get('Team Member 2 Name', ''))
        member3_name = clean_name(row.get('Team Member  1 Email id', ''))  # Note: some CSV issues
        
        # Skip if essential data is missing
        if not team_name or not leader_name or not leader_phone:
            continue
        
        # Skip header rows or empty rows
        if 'OFFLINE' in team_name.upper() or 'INTERNAL' in team_name.upper():
            continue
        if team_name.lower() in ['team name', 'reporting time']:
            continue
        
        # Ensure 10-digit phone
        if len(leader_phone) != 10:
            continue
        
        teams.append({
            'raw_team_name': team_name,
            'leader_name': leader_name,
            'leader_phone': leader_phone,
            'member_2': member1_name,
            'member_3': member2_name,
            'member_4': '',
            'college': college
        })

# Disambiguate duplicate team names
seen_names = {}
processed_teams = []
for t in teams:
    name = t['raw_team_name']
    if name in seen_names:
        seen_names[name] += 1
        unique_name = f"{name} ({seen_names[name]})"
    else:
        seen_names[name] = 1
        unique_name = name
        
    processed_teams.append({
        'team_name': unique_name,
        'leader_name': t['leader_name'],
        'leader_phone': t['leader_phone'],
        'member_2': t['member_2'],
        'member_3': t['member_3'],
        'member_4': t['member_4'],
        'college': t['college']
    })

teams = processed_teams

# Write to CSV
with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'team_name', 'leader_name', 'leader_phone', 
        'member_2', 'member_3', 'member_4', 'college'
    ])
    writer.writeheader()
    writer.writerows(teams)

print(f"[OK] Created {output_file} with {len(teams)} teams")
print(f"\nFirst 3 teams:")
for i, team in enumerate(teams[:3], 1):
    print(f"  {i}. {team['team_name']} - Leader: {team['leader_name']} - Phone: {team['leader_phone']}")

print(f"\nLast 3 teams:")
for i, team in enumerate(teams[-3:], len(teams)-2):
    print(f"  {i}. {team['team_name']} - Leader: {team['leader_name']} - Phone: {team['leader_phone']}")

print(f"\n{'='*60}")
print("LOGIN CREDENTIALS:")
print("  Username (Team Name): [From CSV]")
print("  Password (Leader Phone): [10-digit number]")
print(f"{'='*60}")
print(f"\nExample Login:")
print(f"  Team: {teams[0]['team_name']}")
print(f"  Phone: {teams[0]['leader_phone']}")
