import httpx

url = "https://api.telegram.org/bot<токен>/getMe"

with httpx.Client(timeout=10) as client:
    r = client.get(url)
    print(r.status_code, r.json())