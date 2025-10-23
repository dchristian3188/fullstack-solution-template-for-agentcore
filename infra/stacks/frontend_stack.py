# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
from pathlib import Path

from aws_cdk import (
    Aws,
    BundlingOptions,
    CfnOutput,
    DockerImage,
    Duration,
    NestedStack,
    RemovalPolicy,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_ssm as ssm


class GASPFrontendStack(NestedStack):
    def __init__(
        self,
        scope,
        props: dict,
        **kwargs,
    ):
        self.props = props
        construct_id = props["stack_name_base"] + "-frontend"
        description = "GenAIID AgentCore Starter Pack - React Frontend stack"
        super().__init__(scope, construct_id, description=description, **kwargs)

        self.fe_stack_name = construct_id

        # Read configuration from SSM (created by backend stack)
        self.read_config_from_ssm()

        # Create S3 bucket for static website hosting
        self.create_website_bucket()

        # Create CloudFront distribution
        self.create_cloudfront_distribution()

        # Deploy React application with configuration
        self.deploy_react_app()

        # Output important values
        self.create_outputs()

    def create_website_bucket(self):
        """Create S3 bucket for static website hosting."""
        self.website_bucket = s3.Bucket(
            self,
            f"{self.fe_stack_name}-website-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            auto_delete_objects=True,
            website_index_document="index.html",
            website_error_document="index.html",  # SPA routing support
        )

    def create_cloudfront_distribution(self):
        """Create CloudFront distribution for the React app."""
        # Create Origin Access Control (OAC) for S3
        self.origin_access_control = cloudfront.S3OriginAccessControl(
            self,
            f"{self.fe_stack_name}-s3-oac",
            description="OAC for GenAIID AgentCore Starter Pack React frontend",
        )

        # Create S3 origin
        s3_origin = origins.S3BucketOrigin.with_origin_access_control(
            self.website_bucket,
            origin_access_control=self.origin_access_control,
        )

        self.distribution = cloudfront.Distribution(
            self,
            f"{self.fe_stack_name}-distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                compress=True,
            ),
            # SPA routing support - redirect 404s to index.html
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
        )

        # Grant CloudFront access to S3 bucket
        self.website_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudFrontServicePrincipal",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["s3:GetObject"],
                resources=[f"{self.website_bucket.bucket_arn}/*"],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{Aws.ACCOUNT_ID}:distribution/{self.distribution.distribution_id}"
                    }
                },
            )
        )

        # Note: Cognito callback URLs are configured in the backend stack

    def deploy_react_app(self):
        """Build and deploy the React application to S3."""
        app_path = os.path.join(Path(__file__).parent.parent.parent, "frontend")

        # Generate aws-exports.json configuration following ReVIEW pattern
        exports_config = {
            "Auth": {
                "Cognito": {
                    "userPoolClientId": self.user_pool_client_id,
                    "userPoolId": self.user_pool_id,
                    "loginWith": {
                        "oauth": {
                            "domain": self.cognito_domain,
                            "scopes": ["openid", "email", "profile"],
                            "redirectSignIn": [
                                f"https://{self.distribution.distribution_domain_name}"
                            ],
                            "redirectSignOut": [
                                f"https://{self.distribution.distribution_domain_name}"
                            ],
                            "responseType": "code",
                        },
                        "username": True,
                        "email": True,
                        "phone": False,
                    },
                }
            },
            "AgentCore": {
                "runtimeArn": self.runtime_arn or "",
                "region": Aws.REGION,
            },
        }

        # Create aws-exports.json as a deployment source
        exports_asset = s3deploy.Source.json_data("aws-exports.json", exports_config)

        # Create React app asset with Docker bundling
        react_asset = s3deploy.Source.asset(
            app_path,
            bundling=BundlingOptions(
                image=DockerImage.from_registry(
                    "public.ecr.aws/sam/build-nodejs18.x:latest"
                ),
                command=[
                    "sh",
                    "-c",
                    " && ".join(
                        [
                            "npm --cache /tmp/.npm install",
                            "npm --cache /tmp/.npm run build",
                            "cp -aur /asset-input/dist/* /asset-output/",
                        ]
                    ),
                ],
            ),
        )

        # Deploy both the React app and configuration
        self.deployment = s3deploy.BucketDeployment(
            self,
            f"{self.fe_stack_name}-deployment",
            sources=[react_asset, exports_asset],
            destination_bucket=self.website_bucket,
            distribution=self.distribution,
            prune=False,  # Don't delete files not in the deployment
        )

    def create_outputs(self):
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            f"{self.fe_stack_name}-FrontendUrl",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="Frontend URL",
        )

        CfnOutput(
            self,
            f"{self.fe_stack_name}-UserPoolId",
            value=self.user_pool_id,
            description="Cognito User Pool ID",
        )

        CfnOutput(
            self,
            f"{self.fe_stack_name}-UserPoolClientId",
            value=self.user_pool_client_id,
            description="Cognito User Pool Client ID",
        )

        CfnOutput(
            self,
            f"{self.fe_stack_name}-CognitoDomain",
            value=self.cognito_domain,
            description="Cognito Domain",
        )

    def read_config_from_ssm(self):
        """Read all configuration from SSM Parameter Store."""
        # Read Cognito configuration
        self.user_pool_id = ssm.StringParameter.value_for_string_parameter(
            self, f"/{self.props['stack_name_base']}/cognito-user-pool-id"
        )
        self.user_pool_client_id = ssm.StringParameter.value_for_string_parameter(
            self, f"/{self.props['stack_name_base']}/cognito-user-pool-client-id"
        )
        self.cognito_domain = ssm.StringParameter.value_for_string_parameter(
            self, f"/{self.props['stack_name_base']}/cognito-domain"
        )

        # Read runtime ARN
        self.runtime_arn = ssm.StringParameter.value_for_string_parameter(
            self, f"/{self.props['stack_name_base']}/runtime-arn"
        )
