

def get_completion(message, client, model="gpt-4o-mini",temperature=0):
    message = message
    response = client.chat.completions.create(
        model=model,
        messages=message,
        temperature=temperature,
    )
    return response.choices[0].message.content
