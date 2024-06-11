import json
import re

from openai import OpenAI

from mydb import run_select
from myutils import OPENAI_API_KEY, remove_prefix, remove_suffix

client = OpenAI()


def makeres(status, s):
    return json.dumps({"status": status, "msg": s})


def get_file_name_with_id(input_txt, assistance_id, doc_type):
    response_list = None
    try:
        search_engine_assistant = client.beta.assistants.retrieve(assistance_id)

        # Create a thread where the conversation will happen
        thread = client.beta.threads.create()
        print(f'thread_id: {thread.id}')

        # Create the user message and add it to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"{input_txt}"
        )

        # Create the Run, passing in the thread and the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=search_engine_assistant.id
        )

        # Periodically retrieve the Run to check status and see if it has completed
        # Should print "in_progress" several times before completing
        while run.status != "completed":
            keep_retrieving_run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            print(f"Run status: {keep_retrieving_run.status}")

            if keep_retrieving_run.status == "completed":
                print("\n")
                break

        # Retrieve messages added by the Assistant to the thread
        all_messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )

        # Print the messages from the user and the assistant
        response = all_messages.data[0].content[0].text.value
        print(f"User input: {message.content[0].text.value}")
        print(f"Assistant response: {response}")
        json_data = extract_json(response)
        resp = []
        if isinstance(json_data, dict) or json_data is None:
            return json_data
        else:
            unique_files = remove_duplicate_files(json_data)
            if doc_type == "Email":
                email_resp = []
                for file_name in unique_files:
                    file_name = file_name["file_name"]
                    if not file_name.endswith(".docx"):
                        file_name += ".docx"
                    result = get_email_data(file_name)
                    email_resp.append(result[0])
                return email_resp
            for file_name in unique_files:
                file_name = file_name["file_name"]
                if not file_name.endswith(".docx"):
                    file_name += ".docx"
                query = """select doc_id from dcompare.user_doc where user_id=%s and doc_name=%s"""
                result = run_select(query, (2, file_name))
                if result:
                    for row in result:
                        resp.append({"file_name": file_name, "doc_id": row[0]})
            return resp
    except Exception as e:
        print('Error parsing response')
        return makeres("error", str(e))


def remove_duplicate_files(data):
    unique_files = set()
    unique_data = []
    for item in data:
        file_name = item["file_name"]
        if file_name not in unique_files:
            unique_files.add(file_name)
            unique_data.append(item)
    return unique_data


def extract_json(text):
    # Updated pattern to match both JSON objects ({}) and arrays ([])
    pattern = r'(\{.*?\}|\[.*?\])'

    # Using re.DOTALL to make the '.' match newlines as well
    matches = re.findall(pattern, text, re.DOTALL)

    json_obj = None
    for match in matches:
        try:
            json_obj = json.loads(match)
        except json.JSONDecodeError:
            # Handle case where extraction is not a valid JSON
            pass

    return json_obj


def get_email_data(filename):
    query = """select * from dcompare.email_data where cloud_file_name=%s"""
    rows = run_select(query, (filename,))
    formatted_data = [convert_to_dict(item) for item in rows]
    return formatted_data


def convert_to_dict(data):
    subject, body, attachment_name, attachment_content, cloud_file_url, created_time, cloud_file_name, location, \
     experience_level, role, received_date, sender_email = data
    return {"subject": subject, "body": body, "attachment_name": attachment_name,
            "attachment_content": attachment_content, "cloud_file_name": cloud_file_name,
            "received_date": received_date, "sender_email": sender_email}


def get_resume_categories(email_txt):
    from openai import OpenAI
    client = OpenAI(api_key = OPENAI_API_KEY)

    response = client.chat.completions.create(
    model='ft:gpt-3.5-turbo-1106:impressico-business-solutions-pvt-ltd::8n2sL82E',
    messages=[
        {
        "role": "system",
        "content": "You are an resume categorisation assistant. You will be provided with email subject, body and attached resume content of candidate. You need to categorise it based on candidate's current location, current role and experience level. For 0 to 2 years experience, provide 'entry-level', for 2+ to 5 years experience, provide 'mid-level', for 5+ to  10 years experience, provide 'senior-level' and for 10+ years of experience 'executive/director-level'. You need to provide output in the following JSON format with following keys: location, experience_level, current_role"
        },
        {
        "role": "user",
        "content": f"{email_txt}"
        }
    ],
    temperature=1,
    max_tokens=1000
    )
    categories_dict = {}
    if len(response.choices) > 0:
        resp = response.choices[0].message.content
        response_without_prefix = remove_prefix(resp, "```json")
        response_without_prefix_suffix = remove_suffix(response_without_prefix, "```")
        try:
            categories_dict = json.loads(response_without_prefix_suffix)
        except Exception as e:
            print('Error parsing response')
    return categories_dict

