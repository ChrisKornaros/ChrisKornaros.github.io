![login_img](login_img.jpg)


You recently joined a small startup as a junior developer. The product managers have come to you for help improving new user sign-ups for the company's flagship mobile app.

There are lots of invalid and incomplete sign-up attempts crashing the app. Before creating new accounts, you suggest standardizing validation checks by writing reusable Python functions to validate names, emails, passwords, etc. The managers love this idea and task you with coding core validation functions for improving sign-ups. It's your job to write these custom functions to check all user inputs to ensure they meet minimum criteria before account creation to reduce crashes.


```python
# Re-run this cell
# Preloaded data for validating email domain.
top_level_domains = [
    ".org",
    ".net",
    ".edu",
    ".ac",
    ".gov",
    ".com",
    ".io"
]
```


```python
# Start coding here. Use as many cells as you need.
def validate_name(name):
    if type(name) != str:
            return False
    elif len(name) <= 2: 
        return False
    else:
        return True

def validate_email(email):
    if '@' not in email:
        return False
    for domain in top_level_domains:
        if domain in email:
            return True
    return False

```
