# TLDR; An Email Summarizer 📨✨

My kid's school sends so many emails, often times with long, flowery prose. I simply don't have time to read
and digest all the different communication styles and am driven up the wall by the liberal use of 
"as already mentioned in a previous email". Seriously?!? You're going to add 7 words in at least 10 e-mails a week that
add absolutely zero value? Sheesh.

TLDR; is an email summarizer designed to swiftly process emails, 
extract pivotal details, and provide crisp, cogent summaries utilizing OpenAI's GPT model. 
With built-in features to detect events and seamlessly integrate with Gmail, this tool significantly
enhances email management efficiency.

## 🚀 Features

- 📄 Automatic and coherent summarization of emails.
- 📅 Real-time event detection from emails, with effortless integration into Google Calendar.
- 🔄 Rate-limit awareness for efficient OpenAI calls.
- 🧩 Dynamic text chunking for processing lengthy emails.
- 🔐 `.env` support for secure and hassle-free configuration.
- 🌍 Gmail API integration for a complete email processing experience.

## 🛠 Setup & Installation

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/markwbrown/TLDR
    ```
    Navigate to the cloned directory using:
    ```bash
    cd TLDR
    ```

2. **Install Dependencies**:
    Make sure you have `pip` installed. Then, run:
    ```bash
    pip install -r requirements.txt
    ```

3. **Set up a Google Cloud Project**:
    - Visit [Google Cloud Console](https://console.cloud.google.com/).
    - Click the 'Select a project' drop-down, then 'NEW PROJECT', and name it.
    - Follow the prompts to set up the project.

4. **Enable the Gmail API**:
    - In the Google Cloud Console, navigate to the Dashboard.
    - Click "ENABLE APIS AND SERVICES".
    - Search for 'Gmail API' and select it.
    - Click the "ENABLE" button.

5. **Set up your Gmail Labels**:
   - This project uses two labels: "School" and "SchoolProcessed".
   - Go to your Gmail settings (gear icon > See all settings > Labels tab) and create these labels.
   - To automatically apply the "School" label to incoming emails from your kid's school, set up a filter:
     - In Gmail, go to Settings > Filters and Blocked Addresses > Create a new filter.
     - In the "From" field, input the following: `parent1@tld.com OR parent2@tld.net` (adjust with actual email addresses you want summarized. I added all the parents too in case somebody decides to reply all).
     - Click 'Create filter' and then:
       - Check 'Skip the Inbox (Archive it)'.
       - Check 'Apply the label' and select "School" from the dropdown.
       - Check 'Never send it to Spam'.
       - Finally, click 'Create filter'.

6. **Create OAuth 2.0 Credentials**:
    - Back in the Google Cloud Console, navigate to 'Credentials' under the APIs & Services tab.
    - Click 'Create Credentials' and select 'OAuth 2.0 Client ID'.
    - For Application type, select 'Desktop app' and create.

7. **Download the Credentials JSON File**:
    - After creating the OAuth 2.0 credentials, click the download icon (a downward arrow) next to the client ID you created.
    - Save the downloaded file as `credentials.json` in the root of the `TLDR` project directory.

8. **Get OpenAI API Key**:
    - Go to [OpenAI](https://www.openai.com/) and sign up or sign in.
    - Navigate to the API section to generate or retrieve your API key.

9. **Create a `.env` File**:
    - Make a copy of the `.env-sample` file provided in the repository:
      ```bash
      cp .env-sample .env
      ```
    - Open the `.env` file with your favorite text editor.
    - Replace `YOUR_OPENAI_API_KEY_HERE` with your actual OpenAI API key, such that it looks like:
      ```
      OPENAI_API_KEY=your_actual_key_here
      ```

10. **Run the Script**:
    ```bash
    python main.py
    ```

Now you're all set! This will process emails from the "School" label, summarize them, and then apply the "SchoolProcessed" label after processing. You will be prompted to authorize the script the first time you run it. Follow the prompts to authorize the script and you're good to go!

... Ideally this should be run as a cron job, but you can also run it manually.

## 🤝 Contribution
Interested in enhancing this tool? Contributions are always welcome! Please fork the repository and use a feature branch for any changes. Once you're ready, open a pull request and let's take it from there.

## 📜 License
This project is licensed under the MIT License. Dive into the LICENSE file for more details.