import os
import re
from openai import OpenAI
from flask import Flask, render_template, request, jsonify, url_for
from playwright.sync_api import sync_playwright, Error
import atexit

app = Flask(__name__)

# --- Global objects, to be initialized later ---
p = None
browser = None
page = None
client = None

def initialize_services():
    global p, browser, page, client
    if page is not None:
        return
    print("Initializing services for the first time...")
    try:
        OPENROUTER_API_KEY = "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"
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
        print("OpenRouter client configured.")
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.google.com")
        page.screenshot(path="static/screenshot.png")
        print("Playwright initialized.")
    except Exception as e:
        print(f"FATAL: Could not initialize services: {e}")
        page, client = None, None

def extract_playwright_command(text):
    match = re.search(r'page\..*?(\(|\s|$)', text)
    if match:
        for line in text.splitlines():
            if match.group(0) in line:
                return line.strip().replace('`', '')
    return None

def get_ai_command(user_command, page_html):
    if not client:
        raise ConnectionError("OpenRouter client is not configured.")

    truncated_html = page_html[:8000]

    system_prompt = """
    You are an expert in Playwright automation. Your task is to convert a user's natural language command into a single, executable line of Python code using an available Playwright `page` object.

    **CRITICAL INSTRUCTIONS:**
    1.  Your ENTIRE response MUST be ONLY the single line of executable Python code.
    2.  DO NOT include ```python markdown.
    3.  DO NOT include any explanation, conversation, or any text other than the code.
    4.  The code must start with `page.`.

    --- START OF EXAMPLES ---

    **BASIC ACTIONS:**
    - User: "go to wikipedia.org" -> Your Response: page.goto("https://www.wikipedia.org")
    - User: "click on the search button" -> Your Response: page.locator('button[type="submit"]').click()
    - User: "type 'hello world' in the input field named 'q'" -> Your Response: page.locator('input[name="q"]').fill("hello world")

    **INFORMATION EXTRACTION (QUERIES):**
    - User: "what is the text of the main button" -> Your Response: page.locator('button.primary').text_content()
    - User: "what is the page title" -> Your Response: page.title()
    - User: "what is the current url" -> Your Response: page.url
    - User: "get all the links" -> Your Response: [a.get_attribute('href') for a in page.locator('a').all()]
    - User: "does the page contain the word 'Error'?" -> Your Response: page.locator('body').get_by_text('Error').is_visible()

    **ADVANCED INTERACTION:**
    - User: "hover over the 'Products' menu" -> Your Response: page.locator('text=Products').hover()
    - User: "double click the image" -> Your Response: page.locator('img').dblclick()
    - User: "press the Enter key" -> Your Response: page.keyboard.press('Enter')
    - User: "scroll to the bottom" -> Your Response: page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    - User: "select 'Egypt' from the 'country' dropdown" -> Your Response: page.locator('#country').select_option(label='Egypt')
    - User: "check the terms and conditions box" -> Your Response: page.locator('#terms').check()
    - User: "uncheck the newsletter box" -> Your Response: page.locator('#newsletter').uncheck()

    **WAITS AND ASSERTIONS:**
    - User: "wait for the payment button to appear" -> Your Response: page.locator('#pay-button').wait_for()
    - User: "is the logo visible" -> Your Response: page.locator('#logo').is_visible()
    - User: "take a screenshot of just the form" -> Your Response: page.locator('form').screenshot(path='static/element_screenshot.png')

    --- END OF EXAMPLES ---
    """

    user_prompt = f"User command: \"{user_command}\"\n\nPage HTML for context:\n{truncated_html}"

    response = client.chat.completions.create(
      model="deepseek/deepseek-chat",
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
      ]
    )

    raw_response_text = response.choices[0].message.content.strip()
    print(f"Raw AI Response: {raw_response_text}")

    command_code = extract_playwright_command(raw_response_text)

    if command_code is None:
        # Fallback for simple one-liners that regex might miss
        if raw_response_text.startswith('page.'):
            command_code = raw_response_text
        else:
            raise ValueError("Could not extract a valid Playwright command from the AI's response.")

    return command_code

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/command', methods=['POST'])
def handle_command():
    initialize_services()

    if not page or not client:
        return jsonify({
            'reply': 'FATAL ERROR: Backend services could not be initialized.', 'screenshot_path': ''
        }), 500

    user_command = request.json.get('command')
    if not user_command:
        return jsonify({'error': 'No command provided'}), 400

    ai_command_str = "No command generated."
    try:
        page_html = page.content()
        ai_command_str = get_ai_command(user_command, page_html)
        print(f"Executing command: {ai_command_str}")

        # Heuristic to decide if a command is a query or an action
        query_keywords = ['.text_content', '.title', '.url', '.is_visible', 'get_attribute', '.all()']
        is_query = any(keyword in ai_command_str for keyword in query_keywords)

        if is_query:
            result = eval(ai_command_str, {"page": page})
            # Truncate long results
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + '...'
            reply_text = f"Query Result: {result_str}"
        else:
            eval(ai_command_str, {"page": page})
            reply_text = f"Action completed: {ai_command_str}"

    except Exception as e:
        print(f"Error during command execution: {e}")
        reply_text = f"An error occurred: {str(e)}"
        screenshot_url = url_for('static', filename='screenshot.png') + f'?t={os.path.getmtime("static/screenshot.png")}'
        return jsonify({'reply': reply_text, 'screenshot_path': screenshot_url, 'debug_ai_output': ai_command_str})

    screenshot_path = "static/screenshot.png"
    page.screenshot(path=screenshot_path)
    screenshot_url = url_for('static', filename='screenshot.png') + f'?t={os.path.getmtime(screenshot_path)}'
    return jsonify({'reply': reply_text, 'screenshot_path': screenshot_url})

def cleanup():
    global browser, p
    if browser:
        browser.close()
    if p:
        p.stop()
    print("Cleanup complete.")

atexit.register(cleanup)

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(host='0.0.0.0', port=5001, debug=True)
