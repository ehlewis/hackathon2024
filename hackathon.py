import sys
import time
import smtplib
import json
from openai import AzureOpenAI
from dotenv import dotenv_values
from email.mime.text import MIMEText
from simple_salesforce import Salesforce
from email.mime.multipart import MIMEMultipart

config = dotenv_values(".env")

# Salesforce Authentication (replace with your credentials)
sf = Salesforce(instance='ort--hackathon.sandbox.my.salesforce.com',
                username=config.get("SALESFORCE_USERNAME"),
                password=config.get("SALESFORCE_PASSWORD"),
                security_token=config.get("SALESFORCE_TOKEN"),
                domain="test")

print("SalesForce initialized")

client = AzureOpenAI(
  azure_endpoint = "https://ortthackathon.openai.azure.com",
  api_key= config.get("OPEN_API_KEY"),
  api_version="2024-05-01-preview"
)
 
assistant = client.beta.assistants.create(
  model="gpt-4o", # replace with model deployment name.
  instructions="You are working with SalesForce data to try to determine the next best steps for prospective clients in the title insurance industry and how we can get deals closed",
  tools=[],
  tool_resources={},
  temperature=1,
  top_p=1
)


def call_openai(prompt):
    # Create a thread
    thread = client.beta.threads.create()
    
    # Add a user question to the thread
    message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content=prompt # Replace this with your prompt
    )
    
    # Run the thread
    run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id
    )
    
    # Looping until the run completes or fails
    while run.status in ['queued', 'in_progress', 'cancelling']:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            #print(messages)
            return messages.data[0].content[0].text.value
        elif run.status == 'requires_action':
            # the assistant requires calling some functions
            # and submit the tool outputs back to the run
            pass
        else:
            print(run.status)

# Function to fetch customer journey data from Salesforce
def get_salesforce_data(account_id):
    # Fetching customer data from Salesforce (e.g., Account and Opportunity)
    account = sf.Account.get(account_id)
    account_contacts = sf.query(f"select id,name,email__c,(select name,email,(select id,description,status,subject from tasks) from contacts) from account  where id ='{account_id}'")
    
    contacts = []
    tasks = []
    for contact in account_contacts["records"][0]["Contacts"]["records"]:
        contacts.append({"email":contact["Email"],"name":contact["Name"]})
        for task in contact["Tasks"]["records"]:
            tasks.append({"Description":task["Description"],
                          "Subject":task["Status"],
                          "Status":task["Status"],
                          "Contact":contact["Name"]
                          })



    print(contacts)
    # Extract data: Account info
    account_info = {
        "Account Name": account_contacts["records"][0]["Name"],
        "Contacts": contacts,
        "tasks": tasks
    }


    print(account_info)
    
    return account_info

# Function to generate customer journey insights using OpenAI
def generate_journey_insights(account_info):
    # Formulate a prompt for GPT-4
    journey_prompt = f"""
    We are doing a daily update for our agents and are reviewing the following account and its history:
    
    Account Info:
    Name: {account_info["Account Name"]}
    The account has the following contacts: {account_info["Contacts"]}
    
    We have had the past interactions with the company recently:
    """
    
    for opp in account_info["tasks"]:
        journey_prompt += f"""
        - {opp})
        """
    
    journey_prompt += """
    Based on the information above, provide personalized recommendations on the next steps for this account and potential risks.
    """

    # Call OpenAI to generate insights
    response = call_openai(journey_prompt)
    
    # Return the generated insights
    return response

# Function to automate next step execution based on OpenAI insights
def execute_next_steps(account_id, insights):
    # Parse OpenAI insights for actionable steps
    # For this example, let's assume insights come in a form that suggests updating opportunity stage, creating tasks, etc.
    
    if "schedule a final demo" in insights.lower():
        update_opportunity_stage(account_id, 'Demo Scheduled')
        create_sales_task(account_id, "Schedule a final demo with the client")
        send_email_notification(account_id, "Demo Scheduled", "You need to schedule a final demo with the client before the deal closes.")

    if "send personalized content" in insights.lower():
        update_opportunity_stage(account_id, 'Sent Content')
        create_sales_task(account_id, "Send personalized content and case studies to the client.")
        send_email_notification(account_id, "Content Sent", "You need to send personalized content to the client to nurture the relationship.")

    if "offer discount" in insights.lower():
        update_opportunity_stage(account_id, 'Discount Offered')
        create_sales_task(account_id, "Offer a discount to close the deal.")
        send_email_notification(account_id, "Discount Offered", "You need to offer a discount to close the deal.")
    
    print("Next steps have been executed.")

# Function to update opportunity stage in Salesforce
def update_opportunity_stage(account_id, new_stage):
    opportunities = sf.query(f"SELECT Id, StageName FROM Opportunity WHERE AccountId = '{account_id}'")
    for opp in opportunities["records"]:
        opp_id = opp['Id']
        sf.Opportunity.update(opp_id, {
            'StageName': new_stage
        })
        print(f"Updated opportunity {opp_id} to stage: {new_stage}")

# Function to create a task for the sales team
def create_sales_task(account_id, task_subject):
    task = sf.Task.create({
        'Subject': task_subject,
        'Priority': 'High',
        'Status': 'Not Started',
        'WhatId': account_id,  # Linking task to Account
        'OwnerId': 'your_sales_rep_id',  # Sales rep responsible for this task
    })
    print(f"Created task: {task_subject}")

# Function to send an email notification to the sales rep
def send_email_notification(account_id, subject, body):
    # Example email sender configuration
    sender_email = config.get("SENDER_EMAIL")
    receiver_email = config.get("TO_EMAIL")
    password = config.get("EMAIL_PASSWORD")
    
    # Create the email content
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = f"Action Needed for Account {account_id}: {subject}"
    
    # Email body
    message.attach(MIMEText(body, "plain"))
    
    # Send email
    try:
        with smtplib.SMTP(config.get("SMTP_SERVER"), int(config.get("SMTP_PORT"))) as server:
            server.starttls()
            server.login(sender_email, password)
            text = message.as_string()
            server.sendmail(sender_email, receiver_email, text)
        print("Email notification sent.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def follow_up_email(account_info, contact_name):
    prompt = f"""
    We are doing a daily update for our agents and are reviewing the following account and its history:
    
    Account Info:
    Name: {account_info["Account Name"]}
    The account has the following contacts: {account_info["Contacts"]}
    
    We have had the past interactions with the company recently:
    """
    
    for opp in account_info["tasks"]:
        prompt += f"""
        - {opp})
        """
    
    prompt += """
    Based on the information above, write an email to """ + contact_name + """ and nothing else.
    """
    return call_openai(prompt)

# Function to automate customer journey tracking and insights generation
def generate_customer_journey(account_id):
    # Fetch Salesforce Data
    account_info = get_salesforce_data(account_id)
    
    # Generate insights using OpenAI
    insights = generate_journey_insights(account_info)
    print(f"Customer Journey Insights for {account_info['Account Name']}:\n")
    print(insights)

    for x in range(0,6):
            print("Sleeping to avoid rate limiting...")
            time.sleep(10)
    for contact in account_info["Contacts"]:
        email = follow_up_email(account_info, contact["name"])
        print(email)
        for x in range(0,6):
            print("Sleeping to avoid rate limiting...")
            time.sleep(10)
    
    # Execute next steps based on the generated insights
    execute_next_steps(account_id, insights)


# Example usage: Replace with an actual Salesforce Account ID
account_id = '001TH00000DMZkiYAH'
generate_customer_journey(account_id)


output = call_openai("tell me a joke")
print(output.data[0].content[0].text.value)
sys.exit(0)