import subprocess
import boto3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutoReconciler")

def check_cloud_health(region):
    """
    Priority check: Verifies cloud availability constraints before taking action.
    Returns True if the region and instances are healthy.
    """
    try:
        ec2 = boto3.client('ec2', region_name=region)
        
        # Check if instances have impaired status
        status = ec2.describe_instance_status()
        for instance in status.get('InstanceStatuses', []):
            if instance['InstanceState']['Name'] == 'running':
                sys_stat = instance['SystemStatus']['Status']
                inst_stat = instance['InstanceStatus']['Status']
                
                if sys_stat != 'ok' or inst_stat != 'ok':
                    logger.warning(f"Health constraint failed: Instance {instance['InstanceId']} is impaired.")
                    return False
        return True
    except Exception as e:
        logger.error(f"Failed to check cloud health in {region}: {e}")
        return False

def check_terraform_drift(terraform_dir="./terraform"):
    """
    Runs terraform plan to detect out-of-band changes (e.g., manual reboots).
    Returns True if drift is detected.
    """
    try:
        # -detailed-exitcode returns 0 for no changes, 2 for changes present
        result = subprocess.run(
            ["terraform", "plan", "-detailed-exitcode"],
            cwd=terraform_dir,
            capture_output=True,
            text=True
        )
        if result.returncode == 2:
            logger.info("Drift detected: AWS state does not match Terraform state.")
            return True
        elif result.returncode == 0:
            logger.info("Infrastructure is perfectly synced.")
            return False
        else:
            logger.error("Terraform plan failed to execute properly.")
            return False
            
    except Exception as e:
        logger.error(f"Error running Terraform: {e}")
        return False

def trigger_self_healing(terraform_dir="./terraform"):
    """
    Forces AWS back into alignment with the Terraform state.
    """
    logger.info("Initiating self-healing protocol...")
    try:
        subprocess.run(
            ["terraform", "apply", "-auto-approve"],
            cwd=terraform_dir,
            check=True
        )
        logger.info("Self-healing complete. Infrastructure synced.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Self-healing failed during Terraform apply.")
        return False

def run_reconciliation_cycle(regions=["us-east-1", "ap-south-1"]):
    """
    The main engine loop.
    """
    logger.info("Starting auto-reconciliation cycle...")
    
    # 1. Enforce Cloud Health Constraints
    for region in regions:
        if not check_cloud_health(region):
            logger.error(f"Aborting cycle: Unhealthy cloud state detected in {region}.")
            return {"status": "aborted", "reason": f"Health check failed in {region}"}
            
    # 2. Check for drift
    if check_terraform_drift():
        # 3. Heal if necessary
        success = trigger_self_healing()
        return {"status": "healed" if success else "failed"}
        
    return {"status": "synced"}