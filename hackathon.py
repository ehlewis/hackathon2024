import requests
import openai
from simple_salesforce import Salesforce
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Salesforce Authentication (replace with your credentials)
sf = Salesforce(username='your_salesforce_username',
                password='your_salesforce_password',
                security_token='your_salesforce_security_token')

# OpenAI API Key (replace with your key)
openai.api_key = 'your_openai_api_key'

# Function to fetch customer journey data from Salesforce
def get_salesforce_data(account_id):
    # Fetching customer data from Salesforce (e.g., Account and Opportunity)
    account = sf.Account.get(account_id)
    opportunities = sf.query(f"SELECT Id, Name, StageName, CloseDate FROM Opportunity WHERE AccountId = '{account_id}'")
    
    # Extract data: Account info and Opportunities
    account_info = {
        "Account Name": account["Name"],
        "Industry": account.get("Industry", "N/A"),
        "Website": account.get("Website", "N/A"),
    }

    opportunities_data = [{
        "Opportunity Id": opp["Id"],
        "Opportunity Name": opp["Name"],
        "Stage": opp["StageName"],
        "Close Date": opp["CloseDate"]
    } for opp in opportunities["records"]]
    
    return account_info, opportunities_data

# Function to generate customer journey insights using OpenAI
def generate_journey_insights(account_info, opportunities_data):
    # Formulate a prompt for GPT-4
    journey_prompt = f"""
    The customer with the following details has entered the sales pipeline:
    
    Account Info:
    Name: {account_info["Account Name"]}
    Industry: {account_info["Industry"]}
    Website: {account_info["Website"]}
    
    Opportunities:
    """
    
    for opp in opportunities_data:
        journey_prompt += f"""
        - {opp['Opportunity Name']} (Stage: {opp['Stage']} | Close Date: {opp['Close Date']})
        """
    
    journey_prompt += """
    Based on the information above, provide personalized recommendations on the next steps for this account and potential risks.
    """

    # Call OpenAI to generate insights
    response = openai.Completion.create(
        model="gpt-4", 
        prompt=journey_prompt, 
        max_tokens=200, 
        temperature=0.7
    )
    
    # Return the generated insights
    return response.choices[0].text.strip()

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
    sender_email = "your_email@example.com"
    receiver_email = "sales_rep_email@example.com"
    password = "your_email_password"
    
    # Create the email content
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = f"Action Needed for Account {account_id}: {subject}"
    
    # Email body
    message.attach(MIMEText(body, "plain"))
    
    # Send email
    try:
        with smtplib.SMTP("smtp.example.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            text = message.as_string()
            server.sendmail(sender_email, receiver_email, text)
        print("Email notification sent.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Function to automate customer journey tracking and insights generation
def generate_customer_journey(account_id):
    # Fetch Salesforce Data
    account_info, opportunities_data = get_salesforce_data(account_id)
    
    # Generate insights using OpenAI
    insights = generate_journey_insights(account_info, opportunities_data)
    
    # Print the generated insights
    print(f"Customer Journey Insights for {account_info['Account Name']}:\n")
    print(insights)
    
    # Execute next steps based on the generated insights
    execute_next_steps(account_id, insights)

# Example usage: Replace with an actual Salesforce Account ID
account_id = '0012b00000Xz4l7AAB'
generate_customer_journey(account_id)
