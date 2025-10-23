# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import aws_cdk as cdk
from constructs import Construct

from .backend_stack import GASPBackendStack
from .frontend_stack import GASPFrontendStack


class GenAIIDAgentCoreStarterPackStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        props: dict,
        **kwargs,
    ):
        self.props = props
        construct_id = props["stack_name_base"]
        description = "GenAIID AgentCore Starter Pack - Main Stack"
        super().__init__(scope, construct_id, description=description, **kwargs)

        # Deploy backend stack first (creates Cognito + Runtime)
        self.backend_stack = GASPBackendStack(
            self,
            f"{construct_id}-backend",
            config=props,
        )

        # Deploy frontend stack (reads Cognito + Runtime from SSM)
        self.frontend_stack = GASPFrontendStack(
            self,
            props,
        )

        # Add explicit dependency to ensure backend deploys before frontend
        self.frontend_stack.add_dependency(self.backend_stack)

        # Output the CloudFront URL for easy access
        cdk.CfnOutput(
            self,
            "FrontendUrl",
            value=f"https://{self.frontend_stack.distribution.distribution_domain_name}",
            description="Frontend Application URL",
        )
