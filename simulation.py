import os
import firebase_admin
from firebase_admin import credentials, db
import sys
import time
import random
import requests
import urllib.parse
from datetime import datetime

# 🔥 FIREBASE INITIALIZATION
key_path = "serviceAccountKey.json"

if not os.path.exists(key_path):
    print("\n" + "="*60)
    print("🚨 ERROR: serviceAccountKey.json NOT FOUND! 🚨")
    print("="*60)
    print("For local testing, place it here but MAKE SURE it is not uploaded to GitHub or your web server.")
    print("="*60 + "\n")
    sys.exit(1)

cred = credentials.Certificate(key_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://hydrotruck-5feb6-default-rtdb.firebaseio.com/'
})

metrics_ref = db.reference('hydrotrack/metrics')
history_ref = db.reference('hydrotrack/history')
commands_ref = db.reference('hydrotrack/commands')
users_ref = db.reference('users')
settings_ref = db.reference('settings/callmebot')

def send_callmebot_message(phone, apikey, text):
    try:
        # CallMeBot API requires URL-encoded text
        encoded_text = urllib.parse.quote(text)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_text}&apikey={apikey}"
        response = requests.get(url)
        return response.status_code == 200
    except Exception as e:
        print(f"CallMeBot Error: {e}")
        return False

def dispatch_whatsapp_alerts(leak_dist):
    print("📡 Fetching CallMeBot Admin Config...")
    admin_config = settings_ref.get()
    admin_phone = admin_config.get('phone_number') if admin_config else None
    admin_apikey = admin_config.get('apikey') if admin_config else None
    
    print("👥 Fetching users for notification dispatch...")
    users = users_ref.get()
    if not users: return

    time_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # 1. SEND MASTER ADMIN ALERT
    if admin_phone and admin_apikey:
        admin_msg = f"🛡️ *HydroTrack Admin Alert*\n\nCRITICAL SYSTEM SHUTDOWN.\nLeak detected at {leak_dist}km.\nAll affected users notified.\n\n_Timestamp:_\n{time_str}"
        print(f"   -> Sending Admin WhatsApp to {admin_phone}")
        success = send_callmebot_message(admin_phone, admin_apikey, admin_msg)
        print("      ✅ Delivered!" if success else "      ❌ Failed.")

    # 2. SEND USER ALERTS
    for uid, user in users.items():
        user_phone = user.get('phone')
        user_apikey = user.get('callMeBotApiKey')
        
        # We only send if they have the API key configured in their dashboard
        if user.get('whatsappEnabled') is not False and user_phone and user_apikey:
            phone = str(user_phone).strip()
            if not phone.startswith('+'): phone = '+' + phone
            
            # Create notification in DB
            notif_ref = users_ref.child(f"{uid}/notifications").push()
            notif_ref.set({
                'type': "leak",
                'title': "Critical Leak",
                'message': "Leak detected. Valve auto-shutdown activated.",
                'severity': "critical",
                'read': False,
                'whatsappStatus': "pending",
                'timestamp': int(time.time() * 1000)
            })
            
            # Prepare Message
            zone = user.get('zone', 'your network')
            msg_body = f"🚨 *HydroTrack Alert*\n\nLeak detected in {zone}\n\n*Time:*\n{datetime.now().strftime('%I:%M %p')}\n\n*Severity:*\nCRITICAL\n\n*Action:*\nValve auto-shutdown activated. Please inspect immediately.\n\n_Timestamp:_\n{time_str}"
            
            # Send CallMeBot Message
            print(f"   -> Sending WhatsApp to {phone} (UID: {uid[:5]}...)")
            success = send_callmebot_message(phone, user_apikey, msg_body)
            
            if success:
                print(f"      ✅ Delivered!")
                notif_ref.update({'whatsappStatus': 'delivered'})
            else:
                print(f"      ❌ Failed!")
                notif_ref.update({'whatsappStatus': 'failed'})

def run_simulation():
    consumption_total = 142600
    leak_active = False
    current_leak_dist = 0
    workers_deployed = 0
    total_staff = 15
    
    # 🌊 PRESSURE LOGIC
    current_flow_rate = 50.0  # Starting normal flow
    target_normal_flow = 50.0

    # Timer logic for leaks (approx 60s)
    next_leak_time = time.time() + random.randint(45, 75)

    print("🚀 Simulation Live. Pressure systems online.")
    print("💡 The CallMeBot WhatsApp Engine is loaded and waiting for leaks.")

    system_mode_ref = db.reference('hydrotrack/system/mode')

    while True:
        mode = system_mode_ref.get()
        if mode == 'live':
            print("Mode is LIVE. Simulation paused. Awaiting real hardware...")
            time.sleep(10)
            continue

        # 1. 🛑 CHECK FOR RESUME COMMAND
        cmd = commands_ref.get()
        if cmd and cmd.get('resumeCommand') == True:
            print("✅ System Reset: Re-pressurizing pipes...")
            leak_active = False
            current_leak_dist = 0
            workers_deployed = 0
            commands_ref.update({'resumeCommand': False})
            next_leak_time = time.time() + random.randint(45, 75)

        # 2. 🚨 LEAK TRIGGER LOGIC
        if not leak_active and time.time() >= next_leak_time:
            leak_active = True
            current_leak_dist = round(random.uniform(2.5, 12.0), 2)
            workers_deployed = random.randint(4, 7)
            print(f"\n🚨 LEAK DETECTED at {current_leak_dist} km. Closing valves...")
            
            history_ref.push({
                'timestamp': int(time.time()),
                'location': current_leak_dist,
                'zone': random.choice(["Zone A", "Zone B", "Zone C"]),
                'consumption': f"{consumption_total:,}"
            })
            
            # TRIGGER WHATSAPP DISPATCH
            dispatch_whatsapp_alerts(current_leak_dist)

        # 3. 📉 DYNAMIC FLOW RATE CALCULATION
        if leak_active:
            # If leak is active, decline slowly until 0
            if current_flow_rate > 0:
                current_flow_rate -= random.uniform(3.0, 7.0)
                if current_flow_rate < 0: current_flow_rate = 0
        else:
            if current_flow_rate < target_normal_flow:
                current_flow_rate += 10.0 # Fast recovery
            else:
                current_flow_rate = random.uniform(45.0, 55.0)

        # 4. GENERATE OTHER SENSOR DATA
        water_level = random.randint(70, 92)
        consumption_total += random.randint(2, 6)
        available_workers = total_staff - workers_deployed
        status_string = "LEAK DETECTED" if leak_active else "SYSTEM NORMAL"
        
        deployed_list = random.sample(range(1, 11), workers_deployed) if leak_active else []

        # 5. 📤 PUSH TO FIREBASE
        metrics_ref.set({
            'waterLevel': water_level,
            'flowRate': round(current_flow_rate, 1),
            'quality': "PURE",
            'valveStatus': "OPEN" if not leak_active else "CLOSED (AUTO)",
            'leakDistance': current_leak_dist,
            'consumption': consumption_total,
            'workerStatus': f"{workers_deployed} Deployed / {available_workers} Available" if leak_active else f"0 Deployed / {total_staff} Available",
            'deployedCount': workers_deployed if leak_active else 0,
            'deployedList': deployed_list,
            'status': status_string
        })

        time.sleep(3)

if __name__ == "__main__":
    run_simulation()