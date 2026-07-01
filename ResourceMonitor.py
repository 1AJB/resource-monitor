import psutil
import requests
import time
import sqlite3
import os
from dotenv import load_dotenv

### Loading .env file
load_dotenv()

### Getting webhook from .env for Teams
TEAMS_WEBHOOK_URL = os.getenv('TEAMS_WEBHOOK_URL')

### Adding Debug for database entry
DEBUG = False

### Creating Threshholds for CPU, RAM, and DISK. Change these if you'd like
CPU_THRESHOLD = 1
RAM_THRESHOLD = 1
DISK_THRESHOLD = 1

### Creating function to get the top 3 processes in CPU and RAM
def get_top_processes(metric, top_procs=3):
    ### Creating empty list to add processes to
    processes = []

    ### Getting number of CPU cores
    cpu_cores = psutil.cpu_count()

    ### Creating loop that iterates over processes and gives the name, cpu percent, and memory percent. Has an exception for no processes and access denied.
    for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
             pass
    
    ### Wait 1 second so psutil can measure usage again
    time.sleep(1)    

    ### Creating a dictionary to group processes
    grouped = {}
    
    ### Was having trouble with CPU showing 0% for all processes and found out it needs to pass twice
    for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
        try:
            name = proc.info['name']
            value = proc.info[metric]

    ### Skip unknown processes and sytem idle process that was skewing results by showing unused cpu percentage. 
    ### Also added python to the list to not log it when the script is running and testing lower thresholds.
    ### Add more processes if you'd like
            Excluded_Processes = ['System Idle Process', 'python.exe', 'python3.exe']
            if name is None or name in Excluded_Processes:
                continue
            if value is None:
                value = 0
    
    ### Makes sure the metric is cpu_percent and takes the value and divides by cpu cores to get a more accurate value in terms of cpu usage than just based on a single core.
    ### If the metric is ram or disk it doesn't factor in cpu cores
            if metric == 'cpu_percent':
                adjusted_value = value / cpu_cores
            else:
                adjusted_value = value

            ### Grouping the same same process together, was having the same process show multiple times. This way they are grouped together. 
            if name in grouped:
                grouped[name] = grouped[name] + adjusted_value
            else:
                grouped[name] = adjusted_value
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    ### Convert into a list so it can be sorted
    processes = []
    for name, value in grouped.items():
        processes.append({'name': name, metric: value})

    ### Creating a function to get a number value from processes back that can be sorted
    def get_metric_value(process):
        value = process[metric]
        if value is None:
            return 0 
        return value 
    
    ### Sort the processes by using the key which is the value taken from get_metric_value
    sorted_procs = sorted(processes, key=get_metric_value, reverse=True)
    
    ### Return the top 3 sorted processes using slicing
    return sorted_procs[:top_procs]

### Setting up SQLite database
def setup_database():
    ### Connecting to the database file
    connection = sqlite3.connect('Resource_Monitor.db')

    ### Creating a cursor to execute SQL commands
    cursor = connection.cursor()

    ### Creating the table with an IF NOT EXIST clause 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type      TEXT,
            overall_usage   REAL,
            drive           TEXT,
            process_1_name  TEXT,
            process_1_usage REAL,
            process_2_name  TEXT,
            process_2_usage REAL,
            process_3_name  TEXT,
            process_3_usage REAL,
            timestamp       TEXT
        )
    ''')

    ### Saving the changes
    connection.commit()

    return connection

### Creating function to log the alert into the SQLite database
def log_alert(connection, alert_type, overall_usage, top_processes, drive=None):
    cursor = connection.cursor()

    ### The timestamp in the form of YEAR-MONTH-DAY HOUR:MINUTE:SECOND
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    ### List of processes from the get_top_processes function and using slicing to get each process. Need each individual one to add to db columns
    ### Then a safety check to prevent errors, passing None if condition is not met. Such as when there is an alert from DISK 
    p1 = top_processes[0] if len(top_processes) > 0 else None
    p2 = top_processes[1] if len(top_processes) > 1 else None
    p3 = top_processes[2] if len(top_processes) > 2 else None

    # Build the metric key to know which column to put it under
    if alert_type == 'CPU':
        metric = 'cpu_percent'
    elif alert_type == 'RAM':
        metric = 'memory_percent'
    else:
        metric = None  

    ### Inserting into the db with values using ? as a placeholder. 
    ### This also helps prevent SQL Injection because using ? makes SQLite treat values as pure data amd not commands.
    ### Then comes the actual values
    cursor.execute('''
        INSERT INTO alerts (
            alert_type, overall_usage, drive,
            process_1_name, process_1_usage,
            process_2_name, process_2_usage,
            process_3_name, process_3_usage,
            timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        alert_type, overall_usage, drive,
        ### Two seperate values, first one is if p* AND metric exist then get name from p1 dictionary, otherwise None
        ### If p* and metric exist, get the value and round it to 1 decimal place. otherwise None
        p1['name'] if p1 and metric else None, round(p1[metric], 1) if p1 and metric else None,
        p2['name'] if p2 and metric else None, round(p2[metric], 1) if p2 and metric else None,
        p3['name'] if p3 and metric else None, round(p3[metric], 1) if p3 and metric else None,
        timestamp
    ))

    connection.commit()

    ### Get the last row added to db
    cursor.execute('SELECT * FROM alerts ORDER BY event_id DESC LIMIT 1')
    row = cursor.fetchone()
    return row

### Creating function to send teams alert
def send_teams_alert(alerts):
    ### Formating all alerts into one message
    message_text = ""
    for alert in alerts:
        message_text = message_text + alert + "\n\n"

    ### Teams expects a JSON payload in this format
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "FF0000",
        "summary": "Resource Monitor Alert",
        "sections": [{
            "activityTitle": "⚠️ Resource Monitor Alert",
            "activityText": message_text
        }]
    }

    ### Sending the POST request to Teams
    response = requests.post(
        TEAMS_WEBHOOK_URL,
        json=payload
    )

    ### Checking if it works! It originally said failed but still posted because was only checking for a 200 response but have added 202 which means it was Accepted!
    if response.status_code in [200, 202]:
        print("Teams alert sent successfully!")
    else:
        print(f"Failed to send Teams alert. Status code: {response.status_code}")

### Creating a function that gets CPU, RAM, and DISK space as a percentage. Lists top 3 processes and create an alert if the threshold is reached.
def check_resources(connection):
    ### Creating empty list of alerts and db_entries
    db_entries = []
    alerts = []

    ### Gets the measurements, along with a list of drives I have
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    drives = ['C:\\', 'A:\\', 'Z:\\']

    ### If threshold is met, it then gets top processes, logs the alert to the database and appends the entry to db_entries.
    ### Makes a readable string and iterates over loop of processes and strips , and space at end.
    if cpu > CPU_THRESHOLD:
        top = get_top_processes('cpu_percent')
        row = log_alert(connection, 'CPU', cpu, top)
        db_entries.append(row)
        top_str = ""
        for p in top:
            top_str = top_str + p['name'] + " (" + f"{p['cpu_percent']:.1f}" + "%), "
        top_str = top_str.rstrip(", ")
        alerts.append(f"CPU usage is high!: {cpu}%\nTop processes: {top_str}")
    
    ### Same pattern as CPU condition
    if ram > RAM_THRESHOLD:
        top = get_top_processes('memory_percent')
        row = log_alert(connection, 'RAM', ram, top)
        db_entries.append(row)
        top_str = ""
        for p in top:
            top_str = top_str + p['name'] + " (" + f"{p['memory_percent']:.1f}" + "%), "
        top_str = top_str.rstrip(", ")     
        alerts.append(f"RAM usage is high: {ram}%\nTop processes: {top_str}")
    
    ### Uses a loop to iterate over the drives with an exception to prevent crashing incase the drive isn't found for some reason.
    ### Same as CPU and RAM, it creates a db entry and an alert message.
    for drive in drives:
        try:
            disk = psutil.disk_usage(drive).percent
            if disk > DISK_THRESHOLD:
                row = log_alert(connection, 'DISK', disk, [], drive=drive)
                db_entries.append(row) 
                alerts.append(f"Disk {drive} usage is high: {disk}%")
        except FileNotFoundError:
            pass 
    
    ### Returning lists of alerts and db_entries
    return alerts, db_entries

### Creating main block
if __name__ == "__main__":
    connection = setup_database()
    alerts, db_entries = check_resources(connection)

    ### Checking len of alerts and if it is 0 it outputs a message instead of nothing. 
    ### Print alerts if found with a space
    if len(alerts) == 0:
        print("No alerts!")
    else:
        for alert in alerts:
            print(alert + '\n')
        
        ### Sending alert to teams
        send_teams_alert(alerts)
        
        ### printing database entry if DEBUG is set to True
        if DEBUG:
            for entry in db_entries:
                print(f"Database Entry: {entry}")
    
    ### Closes the connection to database
    connection.close()
