# openai_integration.py
import openai
import os

# Configure OpenAI API key
openai.api_key = os.getenv("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")

def predict_with_openai(image_description):
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",  # You might need to update the engine to the latest available version
            prompt=f"Identify the plant disease in the following description: {image_description}",
            temperature=0.5,
            max_tokens=60,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        return response.choices[0].text.strip()
    except Exception as e:
        print(f"Error with OpenAI API: {e}")
        return "Error: Could not process the image with OpenAI."
