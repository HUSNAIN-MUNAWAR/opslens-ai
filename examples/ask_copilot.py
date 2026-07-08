from packages.python_sdk.opslens import OpsLensClient

client = OpsLensClient()
client.authenticate()
answer = client.ask_copilot("Which products are likely to stock out within 14 days?")
print(answer)
