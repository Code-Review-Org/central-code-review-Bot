import os
import requests
from github import Github

# Initialize GitHub API
github_token = os.getenv("GITHUB_TOKEN")
if not github_token:
    print("Error: GITHUB_TOKEN is not set.")
    exit(1)

g = Github(github_token)

# Get PR details
repo_name = os.getenv("GITHUB_REPOSITORY")
pr_number = os.getenv("GITHUB_EVENT_PULL_REQUEST_NUMBER")
if not repo_name or not pr_number:
    print("Error: GITHUB_REPOSITORY or GITHUB_EVENT_PULL_REQUEST_NUMBER is not set.")
    exit(1)

pr_number = int(pr_number)
repo = g.get_repo(repo_name)
pr = repo.get_pull(pr_number)

# Gemini API setup
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    pr.create_issue_comment("Error: GEMINI_API_KEY is not set in the repository secrets.")
    exit(1)

gemini_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"

# Log PR details
print(f"Reviewing PR #{pr_number} in repository {repo_name}")

# Review each file in the PR
for file in pr.get_files():
    patch = file.patch
    if not patch:
        print(f"No patch for file {file.filename}, skipping...")
        continue

    # Allow code files and .txt for testing
    if not file.filename.endswith(('.py', '.js', '.java', '.cpp', '.txt')):
        print(f"Skipping non-code file: {file.filename}")
        continue

    # Log the diff
    print(f"Processing file: {file.filename}")
    print(f"Diff:\n{patch}")

    # Prepare prompt for Gemini
    prompt = f"""
    Analyze the following diff and provide specific, actionable suggestions for improvement. Focus on:
    - Syntax errors: Identify and suggest fixes (if applicable).
    - Bugs: Point out logical errors or potential issues.
    - Content quality: Suggest improvements for clarity or structure (e.g., for text files).
    - Security: Highlight any security vulnerabilities (if applicable).
    - Best practices: Ensure adherence to best practices (e.g., PEP 8 for Python, ES6 for JavaScript, or clear documentation for text files).
    Provide examples where applicable:
    ```diff
    {patch}
    """

    # Call Gemini API
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 500}
    }
    try:
        response = requests.post(
            f"{gemini_endpoint}?key={gemini_api_key}",
            headers=headers,
            json=data
        )
        response.raise_for_status()

        # Log the raw API response
        response_data = response.json()
        print(f"Gemini API response for {file.filename}: {response_data}")

        # Parse response
        if "candidates" in response_data and response_data["candidates"]:
            review = response_data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            review = "Error: No review suggestions provided by Gemini API (empty response)."
            print(f"No candidates in response for {file.filename}")
    except requests.exceptions.RequestException as e:
        review = f"Error: Failed to get review from Gemini API ({str(e)})."
        print(f"API request failed for {file.filename}: {str(e)}")
    except (KeyError, IndexError) as e:
        review = f"Error: Invalid response format from Gemini API ({str(e)})."
        print(f"Response parsing failed for {file.filename}: {str(e)}")
    except Exception as e:
        review = f"Error: Unexpected error during review ({str(e)})."
        print(f"Unexpected error for {file.filename}: {str(e)}")

    # Post comment on PR
    try:
        print(f"Posting comment for {file.filename}: {review}")
        pr.create_issue_comment(f"### Review for {file.filename}\n{review}")
    except Exception as e:
        print(f"Failed to post comment for {file.filename}: {str(e)}")
        exit(1)
