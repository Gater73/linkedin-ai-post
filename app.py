import time, os, threading, requests, schedule
from flask import Flask, request, jsonify, redirect, url_for
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

app = Flask(__name__)

# Global variables for the app state
ollama_model = None
keywords = []
post_interval = 10  # default interval in minutes
linkedin_access_token = None
linkedin_client_id = os.environ['linkedin_client_id']
linkedin_client_secret = os.environ['linkedin_client_secret']
redirect_uri = 'http://localhost:5000/callback'


@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LinkedIn Post Generator</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
    </head>
    <body>
        <section class="section">
            <div class="container">
                <h1 class="title has-text-centered">LinkedIn Post Generator</h1>
                <div class="content">
                    <ol>
                        <li><strong>Step 1:</strong> Configure the app below by setting the Ollama model, interval, and keywords.</li>
                        <li><strong>Step 2:</strong> Log in with LinkedIn to enable posting.</li>
                    </ol>
                </div>
                <form action="/configure" method="POST" class="box">
                    <div class="field">
                        <label class="label">Ollama Model</label>
                        <div class="control">
                            <input class="input" type="text" name="model" placeholder="Enter Ollama model (e.g., GPT-3.5)" required>
                        </div>
                    </div>
                    <div class="field">
                        <label class="label">Post Interval (minutes)</label>
                        <div class="control">
                            <input class="input" type="number" name="interval" placeholder="Enter interval in minutes" min="1" required>
                        </div>
                    </div>
                    <div class="field">
                        <label class="label">Keywords (comma-separated)</label>
                        <div class="control">
                            <input class="input" type="text" name="keywords" placeholder="Enter keywords" required>
                        </div>
                    </div>
                    <div class="field is-grouped is-grouped-right">
                        <div class="control">
                            <button type="submit" class="button is-primary">Save Configuration</button>
                        </div>
                    </div>
                </form>
                <div class="has-text-centered">
                    <a href="/login" class="button is-link">Login with LinkedIn</a>
                </div>
            </div>
        </section>
    </body>
    </html>
    """


@app.route("/configure", methods=["POST"])
def configure():
    global ollama_model, keywords, post_interval
    ollama_model = request.form.get("model")
    post_interval = int(request.form.get("interval", 10))
    keywords = [kw.strip() for kw in request.form.get("keywords", "").split(",")]
    return f"Configuration saved! Model: {ollama_model}, Interval: {post_interval} minutes, Keywords: {', '.join(keywords)}"


@app.route("/login")
def login():
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code&client_id={linkedin_client_id}&redirect_uri={redirect_uri}&scope=w_member_social"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback():
    global linkedin_access_token
    code = request.args.get("code")
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    response = requests.post(token_url, data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': linkedin_client_id,
        'client_secret': linkedin_client_secret
    })
    linkedin_access_token = response.json().get("access_token")
    return "LinkedIn login successful! The app will now generate posts."


def generate_post():
    if not linkedin_access_token or not ollama_model or not keywords:
        print("App is not fully configured.")
        return

    prompt = (
        "You are a skilled copywriter creating viral Linkedin posts. "
        "Write concise, engaging, and professional content on the provided topic, designed to deliver value, "
        "spark engagement, and encourage shares. Keep the tone conversational yet professional, ensuring the post "
        "is attention-grabbing and shareable."
    )
    topic = ", ".join(keywords)

    # Interact with the local Ollama instance
    ollama_url = f"http://localhost:11434/api/generate"
    ollama_response = requests.post(ollama_url, json={
        "model": ollama_model,
        "system_prompt": prompt,
        "prompt": topic
    })

    if ollama_response.status_code != 200:
        print("Error connecting to Ollama:", ollama_response.text)
        return

    post_content = ollama_response.json().get("text", "").strip()
    print("Generated Post:", post_content)

    # Post to LinkedIn
    linkedin_url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {linkedin_access_token}",
        "Content-Type": "application/json"
    }
    post_data = {
        "author": f"urn:li:person:{linkedin_access_token}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": post_content},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    linkedin_response = requests.post(linkedin_url, json=post_data, headers=headers)
    if linkedin_response.status_code == 201:
        print("Post successfully shared on LinkedIn!")
    else:
        print("Failed to post to LinkedIn:", linkedin_response.text)


# Background thread to schedule posts
def schedule_posts():
    schedule.every(post_interval).minutes.do(generate_post)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    threading.Thread(target=schedule_posts, daemon=True).start()
    app.run(port=5000)
