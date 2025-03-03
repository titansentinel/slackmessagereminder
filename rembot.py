import os
import re
import time
from datetime import datetime, timedelta
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()

# Initialize the app with your bot token
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Set the test channel ID - replace with your specific channel ID
TEST_CHANNEL_ID = "C074LNC045C"  # Replace with your actual channel ID

# Dictionary to store pending reminders
reminders = {}

@app.message(re.compile(r"(.*)"))
def message_handler(message, say, client):
    channel_id = message["channel"]

    # Only process messages from the test channel
    if channel_id != TEST_CHANNEL_ID:
        return

    text = message.get("text", "")
    # Normalize text: convert to lower case and replace typographic apostrophes with straight ones
    normalized_text = text.lower().replace("’", "'")
    user_id = message["user"]
    ts = message["ts"]  # Original message timestamp
    thread_ts = message.get("thread_ts", None)  # Check if this is a threaded reply

    # Log the received message details
    print(f"Received message in channel {channel_id}: {text} (thread_ts: {thread_ts})")

    # Check if this message is a reply in a thread (indicating potential cancellation)
    if thread_ts:
        # Iterate over a copy of keys to safely remove reminders during iteration
        for reminder_id in list(reminders.keys()):
            # If the original message timestamp of a reminder matches this thread,
            # consider it as a cancellation signal.
            if reminders[reminder_id]["message_ts"] == thread_ts:
                print(f"Cancelling reminder for thread {thread_ts} due to a new reply.")
                reminders.pop(reminder_id, None)
                say("Reminder cancelled as a new message was received in the thread.")
                # Return early so no further processing occurs
                return

    # Define reminder keywords
    reminder_keywords = ["follow up", "remind", "don't forget", "check later"]
    # Find user mentions in the message (formatted like <@USERID>)
    mentioned_users = re.findall(r"<@([\w]+)>", text)

    # Check if the message contains any of the reminder keywords and has mentioned users
    if any(keyword in normalized_text for keyword in reminder_keywords) and mentioned_users:
        # For testing, set a short reminder time (1 minute from now)
        reminder_time = datetime.now() + timedelta(minutes=1)

        # Store the reminder for each mentioned user
        for mentioned_user in mentioned_users:
            reminder_id = f"{channel_id}_{ts}_{mentioned_user}"
            reminders[reminder_id] = {
                "channel": channel_id,
                "user": mentioned_user,
                "message_ts": ts,
                "reminder_time": reminder_time,
                "set_by": user_id
            }

            # React to the original message to indicate a reminder was set
            client.reactions_add(
                channel=channel_id,
                timestamp=ts,
                name="alarm_clock"
            )

            # Notify in the channel that a reminder was set
            print(f"Reminder set for user {mentioned_user} at {reminder_time}")

# Function to check and send due reminders
def check_reminders(client):
    current_time = datetime.now()
    reminders_to_remove = []

    for reminder_id, reminder in reminders.items():
        if current_time >= reminder["reminder_time"]:
            try:
                # Send the reminder as a threaded message to the original message
                client.chat_postMessage(
                    channel=reminder["channel"],
                    text=f"<@{reminder['user']}> Reminding you about this message!",
                    thread_ts=reminder["message_ts"]
                )
                print(f"Reminder sent to {reminder['user']} in channel {reminder['channel']}")
            except Exception as e:
                print(f"Error sending reminder: {e}")
            reminders_to_remove.append(reminder_id)

    # Remove reminders that have been processed
    for reminder_id in reminders_to_remove:
        reminders.pop(reminder_id, None)

# Main execution
if __name__ == "__main__":
    print(f"Starting Slack Reminder Bot in TEST MODE for channel {TEST_CHANNEL_ID}")
    print("Bot will monitor this channel only.")

    # Start the Socket Mode handler in a daemon thread
    import threading
    threading.Thread(
        target=lambda: SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start(),
        daemon=True
    ).start()

    # Check for due reminders every 5 seconds (more frequent for testing)
    print("Checking for reminders every 5 seconds...")
    try:
        while True:
            check_reminders(app.client)
            time.sleep(5)  # Sleep for 5 seconds between checks
    except KeyboardInterrupt:
        print("Bot stopped by user")
