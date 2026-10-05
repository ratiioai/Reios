"""
Import real teams directly into database from CSV
Run this script to create all teams and assign questions
"""
import sys
import csv
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Team
from app.auth import hash_phone
import app.question_assignment as question_assignment

# Create tables
Base.metadata.create_all(bind=engine)

def import_teams(auto_clear=True):
    """Import teams from CSV and assign questions"""
    import os
    csv_file = "teams_real.csv"
    if not os.path.exists(csv_file):
        csv_file = "teams_from_form.csv"
    
    db: Session = SessionLocal()
    
    try:
        print(f"Reading teams from {csv_file}...")
        
        teams_data = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                teams_data.append(row)
        
        print(f"Found {len(teams_data)} teams to import")
        
        # Check for existing teams
        existing_count = db.query(Team).count()
        if existing_count > 0:
            print(f"Database already has {existing_count} teams, refreshing with updated CSV data...")
            # Clear used question sets and question assignments first to avoid FK constraints
            from app.models import TeamQuestionAssignment, UsedQuestionSet, Submission
            db.query(Submission).delete()
            db.query(TeamQuestionAssignment).delete()
            db.query(UsedQuestionSet).delete()
            db.query(Team).delete()
            db.commit()
            print("Existing teams cleared")
        
        # Import teams
        print("\nCreating teams...")
        created_teams = []
        
        for i, row in enumerate(teams_data, 1):
            team_name = row['team_name']
            leader_phone = row['leader_phone']
            
            # Create team
            team = Team(
                team_name=team_name,
                leader_name=row['leader_name'],
                leader_phone_hash=hash_phone(leader_phone),
                member_2=row.get('member_2', ''),
                member_3=row.get('member_3', ''),
                member_4=row.get('member_4', ''),
                college=row.get('college', ''),
                csv_row_ref=i,
                is_active=True,
                failed_login_attempts=0
            )
            
            db.add(team)
            created_teams.append({
                'team': team,
                'plain_phone': leader_phone
            })
            
            if i % 10 == 0:
                print(f"   Created {i}/{len(teams_data)} teams...")
        
        # Commit teams
        db.commit()
        print(f"[OK] Created {len(created_teams)} teams")
        
        # Refresh to get IDs
        for item in created_teams:
            db.refresh(item['team'])
        
        # Assign question sets
        print("\nAssigning unique question sets...")
        assigned_count = 0
        failed_assignments = []
        
        for i, item in enumerate(created_teams, 1):
            team = item['team']
            try:
                success = question_assignment.assign_unique_question_set(db, team)
                if success:
                    assigned_count += 1
                else:
                    failed_assignments.append(team.team_name)
                
                if i % 10 == 0:
                    print(f"   Assigned {i}/{len(created_teams)} teams...")
            except Exception as e:
                print(f"   [FAIL] Error assigning to {team.team_name}: {e}")
                failed_assignments.append(team.team_name)
        
        print(f"\n[OK] Successfully assigned questions to {assigned_count}/{len(created_teams)} teams")
        
        if failed_assignments:
            print(f"[WARN] Failed assignments: {len(failed_assignments)}")
            for name in failed_assignments[:10]:
                print(f"   - {name}")
        
        # Show sample credentials
        print("\n" + "="*80)
        print("SAMPLE TEAM CREDENTIALS (First 10)")
        print("="*80)
        
        for i, item in enumerate(created_teams[:10], 1):
            team = item['team']
            phone = item['plain_phone']
            print(f"\n{i}. {team.team_name}")
            print(f"   Username: {team.team_name}")
            print(f"   Password: {phone}")
            print(f"   Leader: {team.leader_name}")
            print(f"   College: {team.college}")
        
        print("\n" + "="*80)
        print(f"[SUCCESS] IMPORT COMPLETE!")
        print(f"   * Teams created: {len(created_teams)}")
        print(f"   * Questions assigned: {assigned_count}")
        print(f"   * Ready for testing!")
        print("="*80)
        
    except FileNotFoundError:
        print(f"[ERROR] Error: {csv_file} not found!")
        print("   Make sure you're running this from the backend directory")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error during import: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    print("="*80)
    print("  SPEC INDUSTRY HACK - TEAM IMPORT")
    print("="*80)
    print()
    
    import_teams()
