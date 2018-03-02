from __future__ import print_function
import json
import boto3
import logging
import time
import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    #logger.info('Event: ' + str(event))
    #print('Received event: ' + json.dumps(event, indent=2))

    ids = []
    vol_ids = []
    start_ids = []
    instance_created_ids = []
    new_vol_ids = []
    run_vol_ids = []

    try:
        region = event['region']
        detail = event['detail']
        eventname = detail['eventName']
        arn = detail['userIdentity']['arn']
        principal = detail['userIdentity']['principalId']
        userType = detail['userIdentity']['type']
        eventTime = detail['eventTime']

        if userType == 'IAMUser':
            user = detail['userIdentity']['userName']

        else:
            user = principal.split(':')[1]


        logger.info('principalId: ' + str(principal))
        logger.info('region: ' + str(region))
        logger.info('eventName: ' + str(eventname))
        logger.info('detail: ' + str(detail))

        if not detail['responseElements']:
            logger.warning('Not responseElements found')
            if detail['errorCode']:
                logger.error('errorCode: ' + detail['errorCode'])
            if detail['errorMessage']:
                logger.error('errorMessage: ' + detail['errorMessage'])
            return False

        ec2 = boto3.resource('ec2')

        if eventname == 'CreateVolume':
            new_vol_ids.append(detail['responseElements']['volumeId'])
            if detail['responseElements']['encrypted'] == False:
                encrypted = "false"
            else:
                encrypted = "true"
            logger.info(new_vol_ids)

        elif eventname == 'RunInstances':
            items = detail['responseElements']['instancesSet']['items']
            for item in items:
                instance_created_ids.append(item['instanceId'])
            logger.info(instance_created_ids)
            logger.info('number of instances: ' + str(len(instance_created_ids)))

            base = ec2.instances.filter(InstanceIds=instance_created_ids)

            #loop through the instances
            for instance in base:
                for vol in instance.volumes.all():
                    run_vol_ids.append(vol.id)
                for eni in instance.network_interfaces:
                    ids.append(eni.id)
                if run_vol_ids:
                    for volumeid in run_vol_ids:
                        print('Tagging new combo Volume resource ' + volumeid)
                    instanceStr = str(instance.id)
                    ec2.create_tags(Resources=run_vol_ids, Tags=[{'Key': 'Creator', 'Value': user}, {'Key': 'PrincipalId', 'Value': principal}, {'Key': 'Created', 'Value': eventTime}, {'Key': 'Name', 'Value': instanceStr}, {'Key': 'Instance', 'Value': instanceStr}])

        elif eventname == 'CreateImage':
            ids.append(detail['responseElements']['imageId'])
            logger.info(ids)
            instances = []
            instances = instances.append(detail['requestParameters']['instanceId'])
            iid = str(detail['responseElements']['imageId'])
            logger.info('ImageId: ' + iid)
            image = ec2.Image(iid).block_device_mappings
            logger.info('Image Devices: ' + str(image))
            for i in image:
                try:
                    snap = i['Ebs']['SnapshotId']
                    mount = i['DeviceName']
                    logger.info('SnapshotId: ' + snap)
                    logger.info('Mount Point: ' + mount)
                    ec2.create_tags(Resources=ids, Tags=[{'Key': mount, 'Value': snap}])
                except Exception as e:
                    logger.info('Error: ' + str(e))
                    pass

        elif eventname == 'CreateSnapshot':
            ids.append(detail['responseElements']['snapshotId'])
            logger.info(ids)
            
        elif eventname == 'AttachVolume':
            volumeId = detail['responseElements']['volumeId']
            try:
                instanceId = detail['responseElements']['instanceId']
            except Exception as e:
                logger.info('instanceId not defined')
                return False
            vol_ids.append(detail['responseElements']['volumeId'])
            logger.info(vol_ids)
            
        elif eventname == 'DetachVolume':
            volumeId = detail['responseElements']['volumeId']
            try:
                instanceId = detail['responseElements']['instanceId']
            except Exception as e:
                logger.info('instanceId not defined')
                return False
            vol_ids.append(detail['responseElements']['volumeId'])
            logger.info(vol_ids)
            
        elif eventname == 'StartInstances':
            items = detail['responseElements']['instancesSet']['items']
            for item in items:
                start_ids.append(item['instanceId'])
            logger.info(start_ids)
            logger.info('number of instances: ' + str(len(start_ids)))
            
        else:
            logger.warning('Not supported action')

        if ids:
            for resourceid in ids:
                print('Tagging standard archive resource ' + resourceid)
            ec2.create_tags(Resources=ids, Tags=[{'Key': 'Creator', 'Value': user}, {'Key': 'PrincipalId', 'Value': principal}, {'Key': 'Occurred', 'Value': eventTime}])

        if instance_created_ids:
            for resourceid in instance_created_ids:
                print('Tagging new EC2 resource ' + resourceid)
            ec2.create_tags(Resources=instance_created_ids, Tags=[{'Key': 'Creator', 'Value': user}, {'Key': 'PrincipalId', 'Value': principal}, {'Key': 'Created', 'Value': eventTime}])
        
        if new_vol_ids:
            for volumeid in new_vol_ids:
                print('Tagging explicit Volume resource ' + volumeid)
            ec2.create_tags(Resources=new_vol_ids, Tags=[{'Key': 'Creator', 'Value': user}, {'Key': 'PrincipalId', 'Value': principal}, {'Key': 'Created', 'Value': eventTime}, {'Key': 'Encrypted', 'Value': encrypted}])

        if vol_ids:
            for volumeid in vol_ids:
                print('Tagging Volume resource ' + volumeid)
            ec2.create_tags(Resources=vol_ids, Tags=[{'Key': 'LastUser', 'Value': user}, {'Key': 'PrincipalId', 'Value': principal}, {'Key': 'LastAttachedInstance', 'Value': instanceId}, {'Key': 'LastAttachmentTime', 'Value': eventTime}])
            
        if start_ids:
            for startid in start_ids:
                print('Tagging restarted resource ' + startid)
            ec2.create_tags(Resources=start_ids, Tags=[{'Key': 'LastUser', 'Value': user}, {'Key': 'PrincipalId', 'Value': principal}])

        logger.info(' Remaining time (ms): ' + str(context.get_remaining_time_in_millis()) + '\n')
        return True
    except Exception as e:
        logger.error('Something went wrong: ' + str(e))
        return False