# PostgreSQL Setup Guide

## Method 1: Using pgAdmin (Easiest - GUI)

### Step 1: Open pgAdmin

1. Open **pgAdmin** application
2. Enter your master password (if prompted)
3. Connect to **PostgreSQL** server (usually localhost)

### Step 2: Create Database

1. Right-click on **Databases** → **Create** → **Database**
2. Name: `coding_test_db`
3. Click **Save**

### Step 3: Create User

1. Right-click on **Login/Group Roles** → **Create** → **Login/Group Role**
2. **General** tab:
   - Name: `coding_test_user`
3. **Definition** tab:
   - Password: `test123`
4. **Privileges** tab:
   - Check **Can login**
   - Check **Create databases**
5. Click **Save**

### Step 4: Grant Permissions

1. Right-click on `coding_test_db` → **Properties**
2. Go to **Security** tab
3. Click **+** to add privilege
4. Select `coding_test_user`
5. Grant these privileges:
   - **CREATE**
   - **CONNECT**
   - **TEMPORARY**
6. Click **Save**

---

## Method 2: Using SQL Shell (psql)

### Step 1: Open SQL Shell

1. Search for **"SQL Shell (psql)"** in Windows Start Menu
2. Press Enter for all defaults until password prompt
3. Enter your PostgreSQL master password

### Step 2: Run These Commands

```sql
-- Create database
CREATE DATABASE coding_test_db;

-- Create user
CREATE USER coding_test_user WITH PASSWORD 'test123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE coding_test_db TO coding_test_user;

-- Connect to new database
\c coding_test_db

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO coding_test_user;
```

Type `\q` to quit when done.

---

## Method 3: Using Batch Script (Automated)

### Step 1: Run the Setup Script

```powershell
cd "c:\Exam Webpage\coding-test-platform\backend"
.\setup_database.bat
```

When prompted for password, enter your PostgreSQL master password (usually set during installation).

---

## Method 4: Check if PostgreSQL is Installed

If PostgreSQL is not installed:

### Download PostgreSQL:
1. Go to: https://www.postgresql.org/download/windows/
2. Download the installer
3. Run installer
4. **Remember the password you set for user 'postgres'**
5. Default port: 5432 (keep it)
6. After installation, use one of the methods above

---

## Verify Connection

After setup, test the connection:

```powershell
cd "c:\Exam Webpage\coding-test-platform\backend"
python test_db_connection.py
```

Should see: "✅ Database connection successful!"

---

## Common Issues

### Issue 1: "psql: command not found"
**Solution:** PostgreSQL not installed or not in PATH
- Install PostgreSQL from https://www.postgresql.org/download/
- Or use pgAdmin (comes with PostgreSQL)

### Issue 2: "password authentication failed"
**Solution:** Wrong password
- Try your PostgreSQL master password
- Or reset password in pgAdmin

### Issue 3: "could not connect to server"
**Solution:** PostgreSQL service not running
- Windows: Search "Services" → Find "postgresql" → Start it
- Or restart computer

### Issue 4: "database already exists"
**Solution:** Database was created previously
- This is fine! Skip to creating tables
- Or drop existing database: `DROP DATABASE coding_test_db;`

---

## Next Steps After PostgreSQL Setup

1. ✅ Create `.env` file:
   ```powershell
   cd backend
   copy .env.example .env
   ```

2. ✅ Edit `.env` with these values:
   ```env
   DATABASE_URL=postgresql://coding_test_user:test123@localhost:5432/coding_test_db
   SECRET_KEY=o2OhT141yKOco91xWdEmbjv9t5OEStUhu-EQVgXYGsI
   ADMIN_PASSWORD=admin123
   USE_LOCAL_COMPILER=true
   ```

3. ✅ Initialize database tables:
   ```powershell
   venv\Scripts\Activate.ps1
   python -c "from app.database import create_tables; create_tables()"
   ```

4. ✅ Create questions:
   ```powershell
   python create_sample_questions_fast.py
   ```

---

## Quick Test

To verify everything works:

```powershell
# Test database connection
python test_db_connection.py

# Create tables
python -c "from app.database import create_tables; create_tables()"

# Create questions
python create_sample_questions_fast.py
```

If all three succeed, you're ready! 🎉

---

## Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]
```

Your connection string:
```
postgresql://coding_test_user:test123@localhost:5432/coding_test_db
```

---

Need help? Check these files:
- `DEPLOY_NOW.md` - Full deployment guide
- `TONIGHT_DONE.md` - Quick checklist
- `TEST_TOMORROW.md` - Testing procedures

