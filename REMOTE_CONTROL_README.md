# 🎮 Remote Control System - M Pro

## Overview

A complete remote activation control system using Supabase database that allows you to manage all activations from anywhere.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Test Connection

```bash
python test_connection.py
```

### 3. Run the Application

```bash
python remote_activation.py
```

### 4. Open Admin Panel

Simply open `admin_panel.html` in your browser.

## Features

### ✅ Remote Control Capabilities

1. **Block/Unblock Users** - Stop or restore user access instantly
2. **Adjust Time** - Add or reduce activation time remotely
3. **Monitor Activity** - See when users last used the app
4. **Real-time Updates** - Changes apply within 30 seconds
5. **Search & Filter** - Find users quickly
6. **Statistics Dashboard** - View active, expired, and blocked users

### 🔒 Security Features

- Row Level Security (RLS) enabled
- Unique device identification
- Encrypted local storage
- HTTPS secure connections
- Users can only read their own status

## Admin Panel Usage

### Block a User
1. Open `admin_panel.html`
2. Find the user
3. Click "🚫 Block"
4. User's app stops immediately

### Add Time
1. Click "➕ Add Time"
2. Select duration (1 hour to 3 months)
3. Time is added to current expiry

### Reduce Time
1. Click "➖ Reduce Time"
2. Select duration to deduct
3. Time is subtracted from current expiry

### Unblock User
1. Click "✅ Unblock"
2. User can use app again

## Database Access

### Via Supabase Dashboard

1. Visit: https://supabase.com/dashboard
2. Login and select your project
3. Go to "Table Editor" → "activations"
4. Directly edit any field:
   - `is_blocked`: true/false
   - `activated`: true/false
   - `expiry`: timestamp or NULL (lifetime)

## Activation Codes

```python
"maf1a01"    → 1 hour
"maf1a07"    → 7 days
"maf1a030"   → 30 days
"maf1a090"   → 90 days
"maf1a0180"  → 180 days
"maf1a0un"   → Lifetime
```

## How It Works

1. **User Activation**:
   - User enters name and activation code
   - Data synced to cloud database
   - Local backup also created

2. **Remote Monitoring**:
   - App checks status every 30 seconds
   - Updates from admin apply immediately
   - Last check time tracked

3. **Admin Control**:
   - Web panel or Supabase dashboard
   - Changes sync to all users
   - Real-time statistics

## Files Structure

```
project/
├── remote_activation.py        # Main application (run this)
├── admin_panel.html            # Web admin interface
├── requirements.txt            # Python dependencies
├── test_connection.py          # Test database connection
├── REMOTE_CONTROL_GUIDE.md     # Detailed Arabic guide
└── REMOTE_CONTROL_README.md    # This file
```

## Database Schema

**Table: activations**

| Field | Type | Description |
|-------|------|-------------|
| id | uuid | Primary key |
| username | text | User's name |
| activation_key | text | Activation code used |
| activated | boolean | Is currently active |
| expiry | timestamptz | Expiration date (NULL = lifetime) |
| is_blocked | boolean | Is user blocked by admin |
| device_id | text | Unique device identifier |
| created_at | timestamptz | When activated |
| last_check | timestamptz | Last time user checked status |

## Troubleshooting

### Connection Issues
- Check internet connection
- Verify Supabase credentials
- Run `test_connection.py`

### Admin Panel Not Loading
- Open browser console (F12)
- Check for JavaScript errors
- Verify Supabase credentials in HTML file

### Changes Not Applying
- Wait 30 seconds (check interval)
- Ensure user has internet connection
- Verify app is running on user's device

## Configuration

### Change Check Interval

Edit in `remote_activation.py`:

```python
REMOTE_CHECK_INTERVAL = 30  # seconds
```

### Supabase Credentials

Located in:
- `remote_activation.py` (lines 75-76)
- `admin_panel.html` (lines 206-207)

## Support

For issues:
1. Check error.txt log file
2. Run test_connection.py
3. Check browser console for admin panel
4. Verify internet connection

## License

This remote control system is built on top of the M Pro application.

---

**🎮 Enjoy full remote control of your application!**

For detailed Arabic guide, see: `REMOTE_CONTROL_GUIDE.md`
