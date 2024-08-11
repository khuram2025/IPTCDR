import requests
from django.http import JsonResponse

def get_3cx_version(request):
    url = "https://smasco.3cx.ae:5001/webclient/api/Login/GetAccessToken"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {
        "SecurityCode": "",
        "Password": "Smasco@445",  # Replace with the actual password
        "Username": "1001"    # Replace with the actual username
    }

    # Step 1: Get the Access Token
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get('Token', {}).get('access_token')
        
        if access_token:
            # Step 2: Use the Access Token to Get 3CX Version
            version_url = "https://smasco.3cx.ae:5001/xapi/v1/Defs?%24select=Id"
            version_headers = {
                "Authorization": f"Bearer {access_token}"
            }

            version_response = requests.get(version_url, headers=version_headers)

            if version_response.status_code == 200:
                version_info = version_response.headers.get("X-3CX-Version")
                return JsonResponse({
                    "status": "success",
                    "version": version_info
                })

            return JsonResponse({
                "status": "error",
                "message": "Failed to retrieve version information"
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": "Failed to retrieve access token"
            })
    else:
        return JsonResponse({
            "status": "error",
            "message": "Authentication failed"
        })

def get_user_groups(request, user_id):
    url = "https://smasco.3cx.ae:5001/webclient/api/Login/GetAccessToken"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {
        "SecurityCode": "",
        "Password": "Smasco@445",  # Replace with the actual password
        "Username": "1001"    # Replace with the actual username
    }

    # Step 1: Get the Access Token
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get('Token', {}).get('access_token')

        if access_token:
            # Step 2: Use the Access Token to Get Groups for the User
            groups_url = f"https://smasco.3cx.ae:5001/Users({user_id})/Groups"
            groups_headers = {
                "Authorization": f"Bearer {access_token}"
            }

            groups_response = requests.get(groups_url, headers=groups_headers)

            if groups_response.status_code == 200:
                groups_list = groups_response.json()
                return JsonResponse({
                    "status": "success",
                    "groups": groups_list
                })

            return JsonResponse({
                "status": "error",
                "message": "Failed to retrieve user groups",
                "details": groups_response.text  # Add this line to see more details
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": "Failed to retrieve access token"
            })
    else:
        return JsonResponse({
            "status": "error",
            "message": "Authentication failed"
        })


def get_users(request):
    # Authentication step (Get the Access Token)
    url = "https://smasco.3cx.ae:5001/webclient/api/Login/GetAccessToken"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {
        "SecurityCode": "",
        "Password": "Smasco@445",  # Replace with the actual password
        "Username": "1001"    # Replace with the actual username
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get('Token', {}).get('access_token')

        if access_token:
            # Use the Access Token to Get List of Users
            users_url = "https://smasco.3cx.ae:5001/Users"
            users_headers = {
                "Authorization": f"Bearer {access_token}"
            }

            users_response = requests.get(users_url, headers=users_headers)

            if users_response.status_code == 200:
                users_list = users_response.json()  # Assuming the response is in JSON format
                return JsonResponse({
                    "status": "success",
                    "users": users_list
                })
            else:
                # Print out the error response for debugging
                return JsonResponse({
                    "status": "error",
                    "message": "Failed to retrieve users information",
                    "details": users_response.text  # Add this line to see more details
                })
        else:
            return JsonResponse({
                "status": "error",
                "message": "Failed to retrieve access token"
            })
    else:
        return JsonResponse({
            "status": "error",
            "message": "Authentication failed"
        })
