import typer
import time
import requests
import igsupload.config as config

def poll_validation_status(doc_id, token, timeout = 300): # timeout so there is no endless loop

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    start_time = time.time()

    while True:
        try:
            response = requests.get(
              f"{config.BASE_URL}/S3Controller/upload/{doc_id}/$validation-status",
              headers=headers, 
              cert=(config.CERT, config.KEY)
            )

            if response.status_code == 200:
                result = response.json()
                status = result.get("status")
                done = result.get("done")
                message = result.get("message")

                color_status = typer.colors.GREEN if status == "VALID" else typer.colors.RED
                color_bool = typer.colors.GREEN if done else typer.colors.RED
                styled_status = typer.style(status, fg=color_status)
                styled_bool = typer.style(done, fg=color_bool)
                
                if message == None:
                  print(f"Current status: {styled_status} (done={styled_bool})")
                else:
                  print(f"Current status: {styled_status} (done={styled_bool}) mit message: {message}")

                if done:
                    print(f"{typer.style('Validation', fg=typer.colors.GREEN)} finished.")
                    return status

            else:
                print(f"{typer.style('Error', fg=typer.colors.RED)}: {response.status_code}")
                print(response.text)

        except requests.RequestException as e:
            print(f"{typer.style('Networkerror', fg=typer.colors.RED)} during polling:", e)

        if time.time() - start_time > timeout:
            print(f"Validation took to long ({typer.style('Timeout', fg=typer.colors.RED)}).")
            return "TIMEOUT"

        # waiting period
        time.sleep(5)
