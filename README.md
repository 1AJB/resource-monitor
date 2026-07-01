# Resource Monitor

A Python-based system resource monitor that tracks CPU, RAM, 
and disk usage and sends real-time alerts to Microsoft Teams 
when thresholds are exceeded. All alerts are logged to a 
SQLite database for historical tracking.

## Features
- Real-time CPU, RAM, and disk monitoring using psutil
- Microsoft Teams notifications via webhook
- SQLite database logging with timestamps
- Top 3 processes identified when CPU or RAM threshold is exceeded
- Configurable thresholds

## Technologies Used
- Python
- psutil
- SQLite3
- Microsoft Teams Webhook API
- python-dotenv

## Setup

1. Clone the repository
2. Install dependencies
3. Create a .env file with your Teams webhook URL
4. Configure thresholds in ResourceMonitor.py
5. Run the script

## Installation

pip install psutil requests python-dotenv

## Configuration

Create a .env file in the project root:
TEAMS_WEBHOOK_URL=your_webhook_url_here

Adjust thresholds at the top of ResourceMonitor.py:
CPU_THRESHOLD = 80
RAM_THRESHOLD = 80
DISK_THRESHOLD = 90

## Screenshots
[Teams Alert]
[Database View]