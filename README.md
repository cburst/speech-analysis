![License](https://img.shields.io/badge/license-Source--Available--Non--Production-blue)
![Python](https://img.shields.io/badge/python-3.11+-blue)

# 🎙️ Speech Analysis Toolkit  
**Azure-Based Pronunciation Assessment + Visualization Tools**

A collection of scripts and web tools for analyzing L2 speech using **Microsoft Azure Pronunciation Assessment**, with support for batch processing, scoring, and visualization.

Includes:

- 🧠 Azure speech processing scripts  
- 📊 Heatmap visualization tools  
- 🌐 Browser-based speech analysis interface  

---

## 🚀 What this repository provides

This repository is **not a packaged application**, but a set of **functional components** that can be used independently or combined in research workflows.

### 🔧 Core Components

- **Azure Processor (Python)**  
  Batch processes audio files using Azure Speech API and extracts:
  - Accuracy
  - Fluency
  - Prosody
  - Completeness

- **Heatmapper (Python)**  
  Generates visual summaries of speech performance:
  - Sentence-level scoring
  - Aggregate heatmaps across speakers

- **Web Interface (Cloudflare Pages)**  
  Lightweight browser-based tool for:
  - Uploading speech samples
  - Running analysis
  - Emailing pronunciation scores

Live demo: https://speech-analysis.pages.dev/

---

## 📁 Repository Structure

```text
speechquality1Lproc.py       → pronunciation processing script
heatmapper.py                → Visualization script
/speech-analysis-site/       → index.html + upload.js
```

---

## ⚙️ Requirements

- Python 3.11+
- Microsoft Azure Speech Service API key
- Google Cloud credentials file for scripts that access Google services
- Required Python libraries listed or imported in the individual scripts

---

## 🔑 Setup

### Azure Configuration

In the Azure processing script, set:

```python
speech_key     = "YOUR API KEY HERE"
service_region = "REGION HERE"
language       = "en-US"
```

### Google Credentials

Pronunciation processing script requires a Google credentials file.

1. Create a Google Cloud service account.
2. Download the JSON credentials file.
3. Place the credentials file somewhere safe on your computer.

---

## 🧪 Typical Workflow

1. Collect audio samples using Google Forms.
2. Run the Azure processor to download speech data and generate pronunciation assessment scores.
3. Use the heatmapper to visualize sentence-level or speaker-level results.

---

## 📊 Output

Depending on the script, outputs may include:

- Sentence-level scoring CSV files
- Aggregate speaker metrics
- Pronunciation, fluency, prosody, and completeness scores
- Heatmap visualizations

---

## 🎯 Research Use

This toolkit supports:

- Pronunciation assessment research
- Human–machine comparison studies
- Classroom-based speech evaluation
- Validation of automated scoring systems
- Exploratory analysis of L2 speech performance

---

## ⚠️ Notes

- Designed for research and educational use.
- Azure scores reflect system-specific calibration and may differ from human rating scales.
- Researchers should validate automated scores within their own instructional or research context before using them for consequential assessment.
- The associated manuscript and dataset will be made publicly available upon publication.

---

## 👤 Author

Richard Rose  
Hankuk University of Foreign Studies (HUFS)

---

## 📄 License

**Source-Available (Non-Production Use Only)**  

Free for personal, educational, and research use.  
Commercial or production use requires a separate license.
