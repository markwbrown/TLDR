import base64
import openai
import re
import time
import tiktoken
import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

load_dotenv()

TOKEN_LIMIT = 180000  # maximum tokens allowed per minute
TOKENS_USED_THIS_MINUTE = 0
START_TIME = time.time()
MAX_TOKENS = 2000  # maximum tokens allowed per API call
BUFFER = 50
CONTEXT_BUFFER = 200  # tokens you reserve for context
RESPONSE_BUFFER = 100
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def call_openai_api(model, messages, estimated_tokens):
    print(f"Calling OpenAI API with {estimated_tokens} tokens")
    global TOKENS_USED_THIS_MINUTE, START_TIME

    # Check if we are about to exceed the rate limit
    if TOKENS_USED_THIS_MINUTE + estimated_tokens > TOKEN_LIMIT:
        elapsed_time = time.time() - START_TIME
        sleep_time = 60 - elapsed_time % 60  # sleep till the next minute starts
        time.sleep(sleep_time)

        # Reset counters after sleeping
        TOKENS_USED_THIS_MINUTE = 0
        START_TIME = time.time()

    # Make the OpenAI API call here
    response = openai.ChatCompletion.create(model=model, messages=messages)
    TOKENS_USED_THIS_MINUTE += estimated_tokens

    return response

def count_tokens(text):
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(text))
    return num_tokens

def split_text_old(text, max_tokens):
    words = text.split()
    current_tokens = 0
    current_chunk = []
    chunks = []

    for word in words:
        word_token_count = count_tokens(word)

        if current_tokens + word_token_count > max_tokens:
            chunks.append(' '.join(current_chunk))
            current_tokens = 0
            current_chunk = []

        current_tokens += word_token_count
        current_chunk.append(word)

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


# def segment_email(email_content):
#     paragraphs = [p.strip() for p in email_content.split('\n') if p.strip()]
#
#     segments = []
#     for paragraph in paragraphs:
#         if count_tokens(paragraph) > MAX_TOKENS - BUFFER:
#             # Splitting the large paragraph further
#             segments.extend(split_large_paragraph(paragraph, MAX_TOKENS - BUFFER))
#         else:
#             segments.append(paragraph)
#
#     return segments
def segment_email(email_content, previous_context=""):
    total_buffer = RESPONSE_BUFFER  # always consider RESPONSE_BUFFER

    if previous_context:
        total_buffer += CONTEXT_BUFFER
        combined_content_tokens = count_tokens(email_content) + count_tokens(previous_context)
    else:
        print(type(email_content), email_content)
        combined_content_tokens = count_tokens(email_content)

    if combined_content_tokens <= MAX_TOKENS - RESPONSE_BUFFER:
        return [email_content]

    # Otherwise, split the email content
    available_tokens = MAX_TOKENS - total_buffer
    return binary_search_split(email_content, available_tokens)
def split_large_paragraph(paragraph, max_tokens):
    words = paragraph.split()
    segments = []
    current_segment = ""

    for word in words:
        if count_tokens(current_segment + word) <= max_tokens:
            current_segment += word + " "
        else:
            segments.append(current_segment.strip())
            current_segment = word + " "

    if current_segment:
        segments.append(current_segment.strip())

    return segments
def split_text(text, max_length):
    """Splits the text into chunks of max_length, ideally at sentence boundaries."""
    sentences = text.split('. ')
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk += ". " + sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
def binary_search_split(text, max_tokens):
    low, high = 0, len(text)
    mid_point = (low + high) // 2

    while low <= mid_point:
        current_subtext = text[low:mid_point]
        if count_tokens(current_subtext) > max_tokens:
            # Current subtext is too large, adjust the high boundary
            high = mid_point
        else:
            # Current subtext fits, adjust the low boundary
            low = mid_point

        mid_point = (low + high) // 2

        # Stop if no further adjustments
        if mid_point == low or mid_point == high:
            break

    # Recurse for remaining text if any
    segments = [text[:mid_point]]
    if mid_point < len(text):
        segments.extend(binary_search_split(text[mid_point:], max_tokens))

    return segments
def send_gmail(subject, body, to_email, service):
    # Create a MIMEText email
    email = MIMEText(body)
    email['to'] = to_email
    email['subject'] = subject
    email['from'] = to_email

    # Encode to base64
    raw_email = base64.urlsafe_b64encode(email.as_bytes()).decode('utf-8')

    # Send the email
    message = service.users().messages().send(userId='me', body={'raw': raw_email}).execute()
    print(f"Message Id: {message['id']}")


def get_email_subject_and_sender(msg):
    headers = msg.get('payload', {}).get('headers', [])
    original_subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)
    sender_full = next((h['value'] for h in headers if h['name'] == 'From'), None)

    # Extracting name using regex
    match = re.match(r'^(.*?)<', sender_full)
    sender_name = match.group(1).strip() if match else sender_full

    return original_subject, sender_name

def get_body_from_message(message):
    print(message)
    if 'parts' in message['payload']:
        print('multipart email')
        # Multipart email, walk through all parts
        for part in message['payload']['parts']:
            print(part)
            mimeType = part.get('mimeType', '')
            if mimeType == 'text/plain':
                print('text/plain')
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif mimeType == 'text/html':
                print('text/html')
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
    else:
        print('simple email or html only')
        # Simple email without parts or HTML only
        return base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
    return None


def modify_email_labels(service, user_id, msg_id, add_label_ids, remove_label_ids):
    body = {
        'addLabelIds': add_label_ids,
        'removeLabelIds': remove_label_ids
    }
    print('removing labels: ', body, ' on message id: ', msg_id, '')
    try:
        service.users().messages().modify(userId=user_id, id=msg_id, body=body).execute()
    except Exception as e:
        print("Error:", e)


# Check if 'gmail-token.json' exists
if os.path.exists('gmail-token.json'):
    creds = Credentials.from_authorized_user_file('gmail-token.json')
else:
    # If not, initiate OAuth 2.0 flow
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify',
    ]
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=8537)
    with open('gmail-token.json', 'w') as token:
        token.write(creds.to_json())

# Initialize Gmail API
service = build('gmail', 'v1', credentials=creds)

labels = service.users().labels().list(userId='me').execute().get('labels', [])
school_label_id = None
processed_label_id = None
for label in labels:
    if label['name'] == "School":
        school_label_id = label['id']
    if label['name'] == "SchoolProcessed":
        processed_label_id = label['id']

print('School Label ID:', school_label_id)
print('Processed Label ID:', processed_label_id)

if school_label_id:
    results = service.users().messages().list(userId='me', labelIds=[school_label_id]).execute()
else:
    print("Couldn't find 'School' label ID.")

messages = results.get('messages', [])
print('Number of emails to process:', len(messages))
# Initialize OpenAI API
openai.api_key = os.environ.get("OPENAI_API_KEY")

for message in messages:
    print('Processing message ID:', message['id'])
    msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
    structuredMsg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()

    msg_id = message['id']
    email_data = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
    mail_body = email_data.decode('utf-8')
    original_subject, sender_name = get_email_subject_and_sender(structuredMsg)
    structured_mail_body = get_body_from_message(structuredMsg)

    # Splitting the text into chunks
    chunks = segment_email(structured_mail_body)
    for idx, segment in enumerate(chunks, 1):
        print(f"Segment {idx}:\n{chunks}\n{'-' * 50}\n")
    # Sending each chunk to the model and collecting results
    results = []
    for chunk in chunks:
        estimated_tokens = 1.5 * (count_tokens(chunk))
        prompt = (f"Summarize the following email (or subsection of an email), ensuring that action items are listed with bullet points. "
                  f"Also, identify any events in the format 'Event Detected: [Event Name] on [Date] at [Time] at [Location]':\n\n{chunk}")
        response = call_openai_api(
            model="gpt-3.5-turbo-16k",
            messages=[{"role": "user", "content": prompt}],
            estimated_tokens=estimated_tokens,
        )
        results.append(response)
        print(f"Response: {response.choices[0].message['content']}\n\n")
    tldr_summary = "\n\n".join([r.choices[0].message['content'] for r in results])
    print(f"Summary: {tldr_summary}\n\n")
    # take the tldr_summary and ask openai to make sure it makes sense
    final_prompt = f"Summarize the following, ensuring bullet points are used and that any links/dates/times/locations are preserved {tldr_summary}"
    final_response = call_openai_api(
        model="gpt-3.5-turbo-16k",
        messages=[{"role": "user", "content": final_prompt}],
        estimated_tokens=1.5*(count_tokens(final_prompt))
    )
    tldr_summary = final_response.choices[0].message['content']

    # Extract event details
    matches = re.findall(r"Event Detected: (.+) on (\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2}) at (.+)", tldr_summary)

    for match in matches:
        event_name = match[0]
        event_date = match[1]
        event_time = match[2]
        event_location = match[3]

        # Generate the Google Calendar link
        calendar_link = (
            f"""<a target="_blank" rel="noopener" href="https://calendar.google.com/calendar/render?action=TEMPLATE&dates={event_date}T{event_time.replace(':', '')}00Z&details={event_name}&location={event_location}&text={event_name}" class="cta btn-yellow" style="background-color: #F4D66C; font-size: 18px; font-family: Helvetica, Arial, sans-serif; font-weight:bold; text-decoration: none; padding: 14px 20px; color: #1D2025; border-radius: 5px; display:inline-block; mso-padding-alt:0; box-shadow:0 3px 6px rgba(0,0,0,.2);"><span style="mso-text-raise:15pt;">Add to your Google Calendar</span></a>""")

        # Replace the event block in the summary with the generated calendar link
        event_block = f"Event Detected: {event_name} on {event_date} at {event_time} at {event_location}"
        tldr_summary = tldr_summary.replace(event_block, calendar_link)
    # Construct the email content
    subject = f"TLDR Summary: {original_subject} - {sender_name}"
    body = f"Summary: {tldr_summary}\n\n"

    # Send the email
    TO_ADDRESS = os.environ.get("TO_ADDRESS")

    send_gmail(subject, body, TO_ADDRESS, service)
    modify_email_labels(service, 'me', msg_id, [processed_label_id], [school_label_id])

    # tldr_summary = response.choices[0].text.strip()
    print(f"Summary: {tldr_summary}\n\n")
