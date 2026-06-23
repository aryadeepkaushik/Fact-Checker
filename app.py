from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import re
import json
from duckduckgo_search import DDGS
import time

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([^&\n?#]+)',
        r'(?:youtu\.be\/)([^&\n?#]+)',
        r'(?:youtube\.com\/embed\/)([^&\n?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/transcribe', methods=['POST'])
def transcribe_video():
    try:
        data = request.json
        youtube_url = data.get('url')
        language = data.get('language', 'hi')
        
        if not youtube_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        video_id = extract_video_id(youtube_url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        try:
            if language == 'hi':
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=['hi', 'en-IN', 'en']
                )
            else:
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=['en', 'en-US', 'en-GB']
                )
            
            transcript = ' '.join([t['text'] for t in transcript_list])
            
            return jsonify({
                'success': True,
                'transcript': transcript,
                'language': language
            })
        except (TranscriptsDisabled, NoTranscriptFound):
            return jsonify({
                'error': 'No captions available. Try a video with captions enabled.'
            }), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/extract-claims', methods=['POST'])
def extract_claims():
    try:
        data = request.json
        transcript = data.get('transcript', '')
        language = data.get('language', 'hi')
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        lang_name = "Hindi" if language == "hi" else "English"
        transcript = transcript[:3000]
        
        prompt = f"""Extract 3-5 fact-checkable claims from this {lang_name} text.
Return ONLY a JSON array. Example: ["Claim 1", "Claim 2"]

Text: {transcript}

JSON array:"""

        response = model.generate_content(prompt)
        claims_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            claims = json.loads(claims_text)
            if not isinstance(claims, list):
                claims = [claims_text]
        except:
            claims = [c.strip().strip('"').strip("'") for c in claims_text.split('\n') if c.strip()]
        
        claims = [c for c in claims if len(c) > 10][:5]
        
        return jsonify({'success': True, 'claims': claims})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-evidence', methods=['POST'])
def search_evidence():
    try:
        data = request.json
        claim = data.get('claim')
        language = data.get('language', 'hi')
        
        if not claim:
            return jsonify({'error': 'No claim provided'}), 400
        
        ddgs = DDGS()
        search_query = claim
        
        if language == 'hi':
            search_query += " news hindi"
        else:
            search_query += " news"
        
        results = ddgs.text(search_query, max_results=5)
        
        evidence = []
        for result in results:
            evidence.append({
                'title': result.get('title', ''),
                'snippet': result.get('body', ''),
                'source': result.get('href', '')
            })
        
        return jsonify({'success': True, 'evidence': evidence})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/verify-claim', methods=['POST'])
def verify_claim():
    try:
        data = request.json
        claim = data.get('claim')
        evidence = data.get('evidence', [])
        language = data.get('language', 'hi')
        
        if not claim:
            return jsonify({'error': 'No claim provided'}), 400
        
        lang_name = "Hindi" if language == "hi" else "English"
        
        evidence_text = "\n\n".join([
            f"Source: {e.get('source', 'Unknown')}\n{e.get('snippet', '')}" 
            for e in evidence[:3]
        ])
        
        prompt = f"""Fact-check this claim in {lang_name}.

Claim: {claim}

Evidence:
{evidence_text}

Return ONLY this JSON format:
{{
    "verdict": "TRUE/FALSE/MISLEADING/UNVERIFIED",
    "confidence": 75,
    "explanation": "Brief explanation in {lang_name}"
}}"""

        response = model.generate_content(prompt)
        result_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(result_text)
        except:
            result = {
                "verdict": "UNVERIFIED",
                "confidence": 50,
                "explanation": result_text[:200]
            }
        
        return jsonify({'success': True, 'result': result})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)