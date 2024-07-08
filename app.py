import csv
import json
import time
import requests
from flask import Flask, render_template, request, jsonify
import os
from PyPDF2 import PdfReader
import re
from urlextract import URLExtract
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# Configure the upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# Function to extract URLs from text using urlextract
def extract_urls(text):
    extractor = URLExtract()
    urls = extractor.find_urls(text)
    print(urls)
    return urls


def extract_stackoverflow_user_ids(text):
    # Regular expression patterns to match Stack Overflow user IDs and shortened URLs
    pattern1 = r'https?://stackoverflow\.com/users/(\d+)/[^\s]+'
    pattern2 = r'https?://stackoverflow\.com/users/(\d+)'

    # Check the first pattern
    user_ids = re.findall(pattern1, text)
    if not user_ids:
        # If no user IDs found with the first pattern, check the second pattern
        user_ids = re.findall(pattern2, text)

    return user_ids


@app.route('/')
def home():
    return render_template('upload.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    try:
        if 'files' not in request.files:
            return "No file part"

        files = request.files.getlist('files')

        if not files or files[0].filename == '':
            return "No selected files"

        results = []

        for file in files:
            if file and file.filename.endswith('.pdf'):
                # Save the uploaded PDF file
                filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filename)

                # Extract text content from the PDF
                pdf_text = ""
                with open(filename, 'rb') as pdf_file:
                    pdf_reader = PdfReader(pdf_file)
                    for page in pdf_reader.pages:
                        pdf_text += page.extract_text()

                # Extract URLs and Stack Overflow user IDs from the text
                urls = extract_urls(pdf_text)
                stackoverflow_ids = extract_stackoverflow_user_ids(pdf_text)

                # Process each Stack Overflow user ID
                for user_id in stackoverflow_ids:
                    process_stackoverflow_user(user_id)

                # Store the results for each file
                results.append({
                    'filename': file.filename,
                    'urls': urls,
                    'stackoverflow_ids': stackoverflow_ids
                })

        return render_template('result.html', results=results)
    except Exception as e:
        return f"An error occurred: {e}"


def question_avg_view_count(user_id):
    base_url = "https://api.stackexchange.com/2.3"
    endpoint = f"/users/{user_id}/questions"
    params = {
        'order': 'desc',
        'sort': 'creation',
        'site': 'stackoverflow',
    }

    response = requests.get(f"{base_url}{endpoint}", params=params)

    if response.status_code == 200:
        user_data = response.json()
        questions = user_data.get('items', [])
        question_count = len(questions)
        total_views = 0

        for question in questions:
            total_views += question.get('view_count', 0)

        # Handle case when there are no questions
        total_avg_views = total_views / question_count if question_count > 0 else 0

        print("avg_views: " + str(total_avg_views), "questions: " + str(question_count))
        return {"total_avg_views": total_avg_views, "question_count": question_count}
    else:
        print(f"Error: {response.status_code}")
        return None


def answer_count(user_id):
    base_url = "https://api.stackexchange.com/2.3"
    endpoint = f"/users/{user_id}/answers"
    params = {
        'order': 'desc',
        'sort': 'creation',
        'site': 'stackoverflow',
    }

    response = requests.get(f"{base_url}{endpoint}", params=params)

    if response.status_code == 200:
        user_data = response.json()
        answer_count = len(user_data.get('items', []))
        return answer_count
    else:
        print(f"Error: {response.status_code}")
        return None


def get_post_data(user_id):
    base_url = "https://api.stackexchange.com/2.3"
    endpoint = f"/users/{user_id}/posts"
    params = {
        'order': 'desc',
        'sort': 'creation',
        'site': 'stackoverflow',
    }

    response = requests.get(f"{base_url}{endpoint}", params=params)

    if response.status_code == 200:
        data = response.json()
        if 'items' in data and len(data['items']) > 0:
            total_score = 0
            total_accept_rate = 0
            post_count = len(data['items'])
            for post in data['items']:
                total_score += post.get('score', 0)
                owner = post.get('owner', {})
                total_accept_rate += owner.get('accept_rate', 0)

            average_score = total_score / post_count
            average_accept_rate = total_accept_rate / post_count

            return {"average_score": average_score, "average_accept_rate": average_accept_rate}
        else:
            print("No posts found for the specified user.")
    else:
        print(f"Error: {response.status_code}")


def get_stackoverflow_user_data(user_id):
    base_url = "https://api.stackexchange.com/2.3"
    endpoint = f"/users/{user_id}"

    params = {
        'order': 'desc',
        'sort': 'reputation',
        'site': 'stackoverflow',
        #'key': api_key,
    }

    response = requests.get(f"{base_url}{endpoint}", params=params)
    if response.status_code == 200:
        user_data = response.json()
        user_item = user_data['items'][0]
        current_timestamp = int(time.time())

        # Calculate the difference in minutes
        last_access_timestamp = user_item.get('last_access_date', 0)
        active_status_min = (current_timestamp - last_access_timestamp) // 60

        filtered_user_data = {
            'UserID': user_item.get('user_id', 'N/A'),
            'Display_Name': user_item.get('display_name', 'N/A'),
            'Reputation': user_item.get('reputation', 'N/A'),
            'Gold_badge': user_item.get('badge_counts', {}).get('gold', 'N/A'),
            'Silver_badge': user_item.get('badge_counts', {}).get('silver', 'N/A'),
            'Bronze_badge': user_item.get('badge_counts', {}).get('bronze', 'N/A'),
            'last_access_date': user_item.get('last_access_date', 'N/A'),
            'current_date': current_timestamp,
            'active_time_difference_min': active_status_min,  # Add active status in minutes
            'reputation_change_year': user_item.get('reputation_change_year', 'N/A'),
            'reputation_change_quarter': user_item.get('reputation_change_quarter', 'N/A'),
            'reputation_change_month': user_item.get('reputation_change_month', 'N/A'),
            'reputation_change_week': user_item.get('reputation_change_week', 'N/A'),
            'reached': user_item.get('reached', 'N/A'),  # Add the reached field
        }
        return filtered_user_data
    else:
        print(f"Error: {response.status_code}")
        return None


def get_user_questions(user_id):
    base_url = "https://api.stackexchange.com/2.3"
    endpoint = f"/users/{user_id}/questions"
    params = {
        'order': 'desc',
        'sort': 'creation',
        'site': 'stackoverflow',
        'filter': 'withbody'
        #'key': api_key,
    }

    response = requests.get(f"{base_url}{endpoint}", params=params)
    if response.status_code == 200:
        user_questions = response.json()
        if 'items' in user_questions:
            questions_details = []  # List to store question details
            for question in user_questions['items']:
                question_details = {
                    'Question ID': question['question_id'],
                    'Title': question['title'],
                    'Creation Date': question['creation_date'],
                    'Score': question['score'],
                    'View Count': question['view_count'],
                    #'Accept Rate':question['accept_rate'],
                    'Tags': ', '.join(question['tags']),
                    'Body': question['body']
                    # Add more fields as needed
                }
                questions_details.append(question_details)
            return questions_details
        else:
            print("No questions found for this user.")
            return []
    else:
        print(f"Error: {response.status_code}")
        return None


def save_to_csv(data, filename):
    """Save user data to a CSV file with separate badge columns."""
    if 'items' in data and data['items']:
        # Collect all keys from all items
        all_keys = set()
        for item in data['items']:
            all_keys.update(item.keys())

        # Convert the set to a list and sort it
        keys = list(all_keys)
        keys.sort()

        # Remove the original 'badge_counts' key and add new keys for individual badges
        if 'badge_counts' in keys:
            keys.remove('badge_counts')
            keys.extend(['gold_badge', 'silver_badge', 'bronze_badge'])

        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=keys)
            writer.writeheader()
            for item in data['items']:
                # Separate the badge counts
                badge_counts = item.pop('badge_counts', {})
                item['gold_badge'] = badge_counts.get('gold', 0)
                item['silver_badge'] = badge_counts.get('silver', 0)
                item['bronze_badge'] = badge_counts.get('bronze', 0)
                writer.writerow(item)
        print(f"Data saved to {full_path}")
    else:
        print("No user data to save.")


def save_to_csv_questions(user_id, questions_data, filename):
    if questions_data:
        keys = ['User ID', 'Question ID', 'Title', 'Creation Date', 'Score', 'View Count', 'Tags', 'Body']
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=keys)
            writer.writeheader()
            for question_details in questions_data:
                question_details['User ID'] = user_id  # Add User ID to each question detail
                writer.writerow(question_details)
        print(f"Data saved to {filename}")
    else:
        print("No questions data to save.")


def process_stackoverflow_user(user_id):
    user_data = get_stackoverflow_user_data(user_id)
    questionCount = question_avg_view_count(user_id)
    answerCount = answer_count(user_id)
    post_data = get_post_data(user_id)
    print(post_data)

    if user_data:
        user_data['question_count'] = questionCount.get('question_count', 0)
        user_data["question_avg_view_count"] = questionCount.get('total_avg_views', 0)
        user_data["answer_count"] = answerCount
        user_data["average_score"] = post_data.get('average_score', 0)
        user_data["average_accept_rate"] = post_data.get('average_accept_rate', 0)
        #user_questions = get_user_questions(user_id)
        print(user_data)
        #print(user_questions)
        if user_data:
            #Add more fields as needed
            save_combined_json_to_csv(user_data, "user_data.csv")
            #save_to_csv(user_data, 'stackoverflow_user_data.csv')
            #save_to_csv_questions(user_id, user_questions, 'stackoverflow_user_questions_data.csv')
        else:
            print("Failed to retrieve user data.")


def save_combined_json_to_csv(data, filename, mode='a'):
    # Check if the file exists and is not empty
    try:
        with open(filename, mode='r', encoding='utf-8') as file:
            is_file_empty = file.read() == ''
    except FileNotFoundError:
        is_file_empty = True

    # Write the data to a CSV file
    with open(filename, mode=mode, newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=data.keys())
        if mode == 'w' or is_file_empty:
            writer.writeheader()
        writer.writerow(data)


if __name__ == '__main__':
    app.run(debug=True)
