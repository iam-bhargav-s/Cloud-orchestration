import boto3
import json
from langchain_core.tools import tool
import subprocess
from langchain_core.tools import tool

@tool
def switch_dashboard_mode(mode: str, action: str = "on") -> str:
    """
    Switches the dashboard viewing mode on or off.
    Args:
        mode: 'finops' or 'latency'.
        action: 'on' or 'off'.
    """
    mode_clean = mode.lower().strip()
    action_clean = action.lower().strip()
    
    if "fin" in mode_clean:
        return f"MODE_SWITCH:finops:{action_clean}"
    elif "lat" in mode_clean or "performance" in mode_clean:
        return f"MODE_SWITCH:latency:{action_clean}"
    return f"Mode '{mode}' not recognized."


@tool
def get_ec2_hourly_price(instance_type: str, region: str = "us-east-1") -> str:
    """
    Fetches the current on-demand hourly price for a specific AWS EC2 instance type.
    Use this tool when evaluating budget constraints before deploying infrastructure.
    """
    try:
        # The AWS Pricing API is specifically hosted in us-east-1 and ap-south-1
        client = boto3.client('pricing', region_name='us-east-1')
        
        response = client.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': 'US East (N. Virginia)'},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'}
            ],
            MaxResults=1
        )
        
        price_list = response.get('PriceList', [])
        if not price_list:
            return f"Could not find pricing for {instance_type} in {region}."
            
        # Parse the nested JSON structure from the AWS Pricing API
        product_data = json.loads(price_list[0])
        terms = product_data.get('terms', {}).get('OnDemand', {})
        
        for term_key, term_value in terms.items():
            price_dimensions = term_value.get('priceDimensions', {})
            for price_key, price_value in price_dimensions.items():
                price_per_unit = price_value.get('pricePerUnit', {}).get('USD')
                return f"The hourly price for {instance_type} in {region} is ${price_per_unit} USD."
                
    except Exception as e:
        return f"Error fetching price: {str(e)}"

@tool
def execute_terraform_deployment(action: str = "apply") -> str:
    """
    Triggers Terraform to initialize and apply or destroy infrastructure.
    Use 'apply' to provision resources or 'destroy' to tear them down safely.
    """
    try:
        if action == "apply":
            # Initialize and apply infrastructure automatically
            init_res = subprocess.run(["terraform", "init"], capture_output=True, text=True, check=True)
            apply_res = subprocess.run(["terraform", "apply", "-auto-approve"], capture_output=True, text=True, check=True)
            return f"Infrastructure deployed successfully!\nLogs: {apply_res.stdout[-300:]}"
        
        elif action == "destroy":
            destroy_res = subprocess.run(["terraform", "destroy", "-auto-approve"], capture_output=True, text=True, check=True)
            return "Infrastructure successfully torn down to prevent charges."
        
        else:
            return "Invalid action. Choose 'apply' or 'destroy'."
            
    except Exception as e:
        return f"Terraform execution failed: {str(e)}"

# Quick local test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print(get_ec2_hourly_price.invoke({"instance_type": "t3.micro"}))