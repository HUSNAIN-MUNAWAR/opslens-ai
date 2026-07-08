from packages.python_sdk.opslens import OpsLensClient

client = OpsLensClient()
client.authenticate("finance@opslens.demo")
print(client.create_report("SDK Margin and Sales Report", "Margin and Sales Report"))
