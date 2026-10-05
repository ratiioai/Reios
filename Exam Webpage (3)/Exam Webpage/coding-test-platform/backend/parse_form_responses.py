"""
Parse Google Form responses and create teams CSV
"""
import csv
import re

# Read the form responses
input_file = r"C:\Exam Webpage\coding-test-platform\SPEC INDUSTRY HACK (Responses) - Form Responses 1.csv"
output_file = r"C:\Exam Webpage\coding-test-platform\backend\teams_from_form.csv"

teams = []
seen_teams = set()

def clean_phone(phone):
    """Extract 10-digit phone number"""
    if not phone:
        return None
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    # Get last 10 digits
    if len(digits) >= 10:
        return digits[-10:]
    return None

def clean_text(text):
    """Clean text fields"""
    if not text:
        return ""
    return text.strip()

print("Reading form responses...")
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    for row in reader:
        team_name = clean_text(row.get('TEAM NAME', ''))
        leader_name = clean_text(row.get('TEAM LEADER NAME', ''))
        leader_phone = clean_phone(row.get('TEAM LEADER MOBILE NUMBER', ''))
        college = clean_text(row.get('TEAM LEADER COLLEGE NAME', ''))
        
        # Get team members
        member_2 = clean_text(row.get('Team Member 1 Name', ''))
        member_3 = clean_text(row.get('Team Member 2 Name', ''))
        member_4 = clean_text(row.get('Team Member 3 Name', ''))  # Form has Team Member 1, 2, but we call them member_2, 3, 4
        
        # Skip if no team name or phone
        if not team_name or not leader_phone:
            continue
        
        # Skip duplicates
        if team_name.lower() in seen_teams:
            print(f"⚠️  Skipping duplicate: {team_name}")
            continue
        
        seen_teams.add(team_name.lower())
        
        teams.append({
            'team_name': team_name,
            'leader_name': leader_name,
            'leader_phone': leader_phone,
            'member_2': member_2,
            'member_3': member_3,
            'member_4': member_4,
            'college': college
        })

print(f"\n✅ Found {len(teams)} unique teams")

# Write to CSV
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['team_name', 'leader_name', 'leader_phone', 'member_2', 'member_3', 'member_4', 'college']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(teams)

print(f"✅ Written to: {output_file}")

# Print first 10 teams as examples
print("\n📋 Sample Teams (first 10):")
print("=" * 80)
for i, team in enumerate(teams[:10], 1):
    print(f"{i}. {team['team_name']}")
    print(f"   Username: {team['team_name']}")
    print(f"   Password: {team['leader_phone']}")
    print(f"   Leader: {team['leader_name']}")
    print(f"   College: {team['college']}")
    print()

print(f"\n✅ Total teams ready: {len(teams)}")
print(f"📄 Output file: {output_file}")
