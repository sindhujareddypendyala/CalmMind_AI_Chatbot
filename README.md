# 🧠 CalmMind AI

### Your Personal Mental Wellness Companion

CalmMind AI is an AI-powered Mental Wellness Companion designed to provide emotional support, stress management guidance, mindfulness techniques, mood tracking, journaling assistance, and personalized wellness recommendations.

The application helps users improve their mental well-being through intelligent conversations powered by Google's Gemini AI.

---

## 🌟 Features

### 💬 AI Wellness Chatbot

* Real-time AI conversations
* Emotional support and guidance
* Stress management assistance
* Anxiety and overthinking support
* Motivation and productivity guidance
* Mental wellness focused responses

### 😊 Mood Tracking

* Daily mood logging
* Mood history tracking
* Emotional trend analysis
* Wellness insights

### 🌬️ Breathing Exercises

* Box Breathing
* 4-7-8 Breathing
* Calm Focus Breathing

### 🎯 Personalized Wellness Plans

* AI-generated wellness routines
* Daily affirmations
* Habit-building recommendations
* Goal-based wellness strategies

### 📄 Wellness Reports

* Mood summaries
* Journal insights
* Wellness recommendations
* PDF report generation


## 🏗️ Tech Stack

### Frontend

* Streamlit

### Backend

* Python

### AI Model

* Groq API

### Database

* SQLite

### Data Visualization

* Plotly

### PDF Reports

* ReportLab

### Environment Management

* Python Dotenv

---

## 📂 Project Structure

```text
CalmMind_AI_Chatbot/

├── app.py
├── requirements.txt
├── .env

├── components/
│   └── sidebar.py

├── database/
│   └── db.py

├── pages/
│   ├── home.py
│   ├── chat.py
│   ├── mood_tracker.py
│   ├── journal_page.py
│   ├── breathing_center.py
│   ├── wellness_plan.py
│   └── reports_page.py

├── services/
│   ├── gemini_service.py
│   ├── mood_detector.py
│   ├── journal_analyzer.py
│   ├── report_generator.py
│   └── voice_service.py

├── prompts/
│   └── system_prompt.py

└── utils/
    ├── helpers.py
    ├── session_manager.py
    └── theme.py
```

---

## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/sindhujareddypendyala/CalmMind_AI_Chatbot.git

cd CalmMind_AI_Chatbot
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

#### Windows

```bash
venv\Scripts\activate
```

#### Linux / Mac

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 Environment Variables

Create a `.env` file in the project root.

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

---

## ▶️ Run Application

```bash
streamlit run app.py
```

Application URL:

```text
http://localhost:8501
```

---

## 💡 Example Prompts

```text
I am feeling stressed about my exams.

I feel anxious about my future.

Can you help me manage overthinking?

I need motivation to stay productive.

Can you suggest a breathing exercise?

Create a wellness plan for me.
```

---

## 🎯 Purpose

CalmMind AI is designed to support users with:

* Stress Management
* Anxiety Support
* Emotional Wellness
* Mindfulness
* Motivation
* Focus Improvement
* Positive Habit Building
* Burnout Recovery

---

## ⚠️ Disclaimer

CalmMind AI is intended for educational and wellness support purposes only.

It does not provide medical diagnoses, prescribe medication, or replace professional mental health care.

If you are experiencing a mental health crisis, please seek immediate assistance from a licensed professional or emergency services.

---

## 🚀 Deployment

This project can be deployed on:

* Streamlit Cloud
* Hugging Face Spaces
* Render

---

## 👩‍💻 Developer

**Sindhuja Reddy**

B.Tech Data Science Student

Built as part of a Generative AI Internship Challenge.

---

### 🧠 CalmMind AI

*"Supporting emotional wellness through responsible AI."*
