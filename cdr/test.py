import requests
import json
import urllib3

# Disable SSL warnings (not recommended for production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Replace these variables with your actual values
PBX_DOMAIN = 'smasco.3cx.ae:5001'  # e.g., 'pbx.example.com' or '192.168.1.100'
USER_NUM = '1001'  # Your extension number for authentication
USER_PASS = 'Smasco@445'  # Your web client password for authentication
TARGET_EXTENSION = '1003'  # The extension you want to modify

def authenticate_user():
    url = f'https://{PBX_DOMAIN}/webclient/api/Login/GetAccessToken'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    payload = {
        "SecurityCode": "",
        "Password": USER_PASS,
        "Username": USER_NUM
    }

    # Print the authentication request details
    print("Authentication Request:")
    print("URL:", url)
    print("Headers:", headers)
    print("Payload:", json.dumps(payload, indent=4))

    response = requests.post(url, headers=headers, json=payload, verify=False)

    # Print the response details
    print("Response Status Code:", response.status_code)
    # Truncate the response text for security
    print("Response Text:", response.text[:100] + '...')

    if response.status_code == 200:
        data = response.json()
        if data.get('Status') == 'AuthSuccess':
            access_token = data['Token']['access_token']
            print("Authentication successful.")
            return access_token
        else:
            print('Authentication failed:', data.get('Status'))
            return None
    else:
        print('Authentication request failed with status code:', response.status_code)
        print('Response:', response.text)
        return None

def get_user_id(access_token, extension_number):
    url = f'https://{PBX_DOMAIN}/xapi/v1/Users'
    params = {
        '$filter': f"Number eq '{extension_number}'"
    }
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    # Print the user ID request details
    print("\nGet User ID Request:")
    print("URL:", url)
    print("Headers:", headers)
    print("Params:", params)

    response = requests.get(url, headers=headers, params=params, verify=False)

    # Print the response details
    print("Response Status Code:", response.status_code)
    print("Response Text:", response.text)

    if response.status_code == 200:
        data = response.json()
        if data['value']:
            user_id = data['value'][0]['Id']
            print(f"User ID for extension {extension_number}: {user_id}")
            return user_id
        else:
            print(f'Extension {extension_number} not found.')
            return None
    else:
        print('Failed to retrieve user ID. Status code:', response.status_code)
        print('Response:', response.text)
        return None

def enable_record_calls(access_token, user_id):
    url = f'https://{PBX_DOMAIN}/xapi/v1/Users({user_id})'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    payload = {
        "Internal": False
    }

    print("\nEnable Record Calls Request:")
    print("URL:", url)
    print("Headers:", headers)
    print("Payload:", json.dumps(payload, indent=4))

    response = requests.patch(url, headers=headers, json=payload, verify=False)

    print("Response Status Code:", response.status_code)
    print("Response Text:", response.text)

    if response.status_code == 200:
        print(f'Successfully enabled call recording for user ID: {user_id}')
    else:
        print('Failed to update user settings. Status code:', response.status_code)
        print('Response:', response.text)

def main():
    # Step 1: Authenticate
    access_token = authenticate_user()
    if not access_token:
        return

    # Step 2: Get User ID of the target extension
    user_id = get_user_id(access_token, TARGET_EXTENSION)
    if not user_id:
        return

    # Step 3: Enable record calls
    enable_record_calls(access_token, user_id)

if __name__ == '__main__':
    main()
