"""
CSV Team Import Handler
Validates and imports teams from CSV file
"""
import re
from typing import List, Dict, Tuple
import pandas as pd
from sqlalchemy.orm import Session

from app.auth import hash_phone
from app.models import Team


class CSVImportError(Exception):
    """Custom exception for CSV import errors"""
    pass


class CSVValidationResult:
    """Result of CSV validation"""
    def __init__(self):
        self.valid_rows: List[Dict] = []
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.total_rows: int = 0
        self.valid_count: int = 0
        self.error_count: int = 0


def validate_phone_format(phone: str) -> bool:
    """
    Validate phone number format
    Accepts: 10 digits, optionally with +91 prefix
    """
    if not phone:
        return False
    
    # Remove spaces and dashes
    phone = phone.replace(" ", "").replace("-", "")
    
    # Check patterns
    patterns = [
        r'^\d{10}$',           # 1234567890
        r'^\+91\d{10}$',       # +911234567890
        r'^91\d{10}$',         # 911234567890
    ]
    
    return any(re.match(pattern, phone) for pattern in patterns)


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to 10 digits
    Removes +91 or 91 prefix
    """
    phone = phone.replace(" ", "").replace("-", "")
    
    if phone.startswith("+91"):
        phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    
    return phone


def validate_csv_structure(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validate CSV has required columns
    Returns: (is_valid, list_of_errors)
    """
    required_columns = ['team_name', 'leader_name', 'leader_phone']
    optional_columns = ['member_2', 'member_3', 'member_4', 'college']
    
    errors = []
    
    # Check required columns
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")
    
    return len(errors) == 0, errors


def validate_csv_data(df: pd.DataFrame, db: Session) -> CSVValidationResult:
    """
    Validate CSV data row by row
    """
    result = CSVValidationResult()
    result.total_rows = len(df)
    
    # Get existing teams for duplicate checking
    existing_teams = {t.team_name.strip().lower() for t in db.query(Team.team_name).all()}
    
    # Track duplicates within the CSV itself
    seen_team_names = set()
    seen_phones = set()
    
    for idx, row in df.iterrows():
        row_number = idx + 2  # +2 because Excel is 1-indexed and has header row
        row_errors = []
        
        # Validate team_name
        team_name = str(row.get('team_name', '')).strip()
        if not team_name:
            row_errors.append("team_name is required")
        elif team_name.lower() in existing_teams:
            row_errors.append(f"team_name '{team_name}' already exists in database")
        elif team_name.lower() in seen_team_names:
            row_errors.append(f"team_name '{team_name}' is duplicated in this CSV")
        else:
            seen_team_names.add(team_name.lower())
        
        # Validate leader_name
        leader_name = str(row.get('leader_name', '')).strip()
        if not leader_name:
            row_errors.append("leader_name is required")
        
        # Validate leader_phone
        leader_phone = str(row.get('leader_phone', '')).strip()
        if not leader_phone:
            row_errors.append("leader_phone is required")
        elif not validate_phone_format(leader_phone):
            row_errors.append(f"leader_phone '{leader_phone}' has invalid format (must be 10 digits)")
        else:
            normalized_phone = normalize_phone(leader_phone)
            if normalized_phone in seen_phones:
                row_errors.append(f"leader_phone '{leader_phone}' is duplicated in this CSV")
            else:
                seen_phones.add(normalized_phone)
        
        # Optional fields (just validate they're strings if present)
        member_2 = str(row.get('member_2', '')).strip() if pd.notna(row.get('member_2')) else None
        member_3 = str(row.get('member_3', '')).strip() if pd.notna(row.get('member_3')) else None
        member_4 = str(row.get('member_4', '')).strip() if pd.notna(row.get('member_4')) else None
        college = str(row.get('college', '')).strip() if pd.notna(row.get('college')) else None
        
        if row_errors:
            result.errors.append({
                'row': row_number,
                'team_name': team_name,
                'errors': row_errors
            })
            result.error_count += 1
        else:
            result.valid_rows.append({
                'row': row_number,
                'team_name': team_name,
                'leader_name': leader_name,
                'leader_phone': normalize_phone(leader_phone),
                'member_2': member_2,
                'member_3': member_3,
                'member_4': member_4,
                'college': college,
            })
            result.valid_count += 1
    
    return result


def import_teams_from_csv(file_path: str, db: Session) -> Dict:
    """
    Import teams from CSV file
    Returns summary of import results
    """
    try:
        # Read CSV
        df = pd.read_csv(file_path)
        
        # Validate structure
        is_valid, structure_errors = validate_csv_structure(df)
        if not is_valid:
            raise CSVImportError(f"Invalid CSV structure: {'; '.join(structure_errors)}")
        
        # Validate data
        validation_result = validate_csv_data(df, db)
        
        # Import valid rows
        imported_teams = []
        for row_data in validation_result.valid_rows:
            team = Team(
                team_name=row_data['team_name'],
                leader_name=row_data['leader_name'],
                leader_phone_hash=hash_phone(row_data['leader_phone']),
                member_2=row_data['member_2'],
                member_3=row_data['member_3'],
                member_4=row_data['member_4'],
                college=row_data['college'],
                csv_row_ref=row_data['row'],
                is_active=True,
                failed_login_attempts=0,
            )
            db.add(team)
            imported_teams.append(team)
        
        db.commit()
        
        return {
            'success': True,
            'total_rows': validation_result.total_rows,
            'imported_count': len(imported_teams),
            'error_count': validation_result.error_count,
            'errors': validation_result.errors,
            'warnings': validation_result.warnings,
        }
        
    except pd.errors.EmptyDataError:
        raise CSVImportError("CSV file is empty")
    except pd.errors.ParserError as e:
        raise CSVImportError(f"CSV parsing error: {str(e)}")
    except Exception as e:
        db.rollback()
        raise CSVImportError(f"Import failed: {str(e)}")


def generate_csv_template() -> pd.DataFrame:
    """Generate a template CSV with sample data"""
    template_data = {
        'team_name': ['Team Alpha', 'Team Beta', 'Team Gamma'],
        'leader_name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
        'leader_phone': ['9876543210', '9123456789', '9988776655'],
        'member_2': ['Alice Brown', 'Charlie Davis', 'Diana Prince'],
        'member_3': ['Eve Wilson', 'Frank Miller', 'Grace Lee'],
        'member_4': ['Henry Ford', 'Ivy Chen', 'Jack Ryan'],
        'college': ['MIT', 'Stanford', 'Harvard'],
    }
    return pd.DataFrame(template_data)
