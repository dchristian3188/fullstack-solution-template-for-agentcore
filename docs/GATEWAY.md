# AgentCore Gateway Implementation

This document describes how GASP implements AgentCore Gateway with Lambda targets to provide a scalable, production-ready tool execution architecture.

## Overview

GASP uses **AgentCore Gateway with Lambda Targets** to enable agents to access external tools and services. This architecture provides a clean separation between agent logic and tool implementation, allowing for independent scaling and deployment of individual tools.

## Architecture Comparison

### Standalone MCP Gateway vs Lambda Targets

There are two primary approaches to implementing AgentCore Gateway:

#### Standalone MCP Gateway
- Gateway directly implements MCP (Model Context Protocol) server
- Tools are built into the gateway infrastructure
- Simpler setup for basic scenarios
- Direct client → gateway communication

#### Lambda Targets (GASP's Choice)
- Gateway acts as a proxy/router to external Lambda functions
- Each tool is implemented as a separate Lambda function
- Client → Gateway → Lambda → Gateway → Client flow
- Production-ready architecture with enterprise benefits

### Why GASP Uses Lambda Targets

We chose Lambda targets for the following production advantages:

1. **Separation of Concerns**: Business logic lives in Lambda functions, not gateway infrastructure
2. **Independent Scaling**: Each tool can scale independently based on usage patterns
3. **Maintainability**: Update tool logic without touching gateway infrastructure
4. **Reusability**: Same Lambda can be used by multiple gateways or other services
5. **Language Flexibility**: Each Lambda can use different programming languages
6. **Independent Deployment**: Deploy tool updates without gateway downtime
7. **Cost Optimization**: Pay only for actual tool execution time
8. **Security**: Each Lambda can have specific IAM permissions for its requirements

## Implementation Details

### Gateway Configuration

The gateway is created with the following configuration:

- **Protocol Type**: MCP (Model Context Protocol)
- **Authorization**: Custom JWT with Cognito integration
- **Authentication**: Machine-to-machine client credentials flow
- **Target Type**: AWS Lambda functions

### Lambda Target Structure

Each Lambda target in GASP follows this pattern:

```python
def handler(event, context):
    # Get tool name from context (strip target prefix)
    delimiter = "___"
    original_tool_name = context.client_context.custom['bedrockAgentCoreToolName']
    tool_name = original_tool_name[original_tool_name.index(delimiter) + len(delimiter):]
    
    # Event contains tool arguments directly
    arguments = event
    
    # Return response in expected format
    return {
        'content': [
            {
                'type': 'text',
                'text': 'Tool response here'
            }
        ]
    }
```

### Tool Schema Definition

Tools are defined using JSON schema in the CDK stack:

```json
{
    "name": "sample_tool",
    "description": "A sample tool that returns a greeting",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name to greet"
            }
        },
        "required": ["name"]
    }
}
```

### Authentication Flow

1. **Machine Client**: CDK creates a Cognito machine client with client credentials flow
2. **Resource Server**: Defines scopes for gateway access (read/write)
3. **JWT Authorization**: Gateway validates tokens using Cognito's OIDC discovery
4. **SSM Parameters**: Client credentials stored securely in SSM Parameter Store

## Key Components

### 1. Gateway Custom Resource

A custom CloudFormation resource manages the gateway lifecycle:

- Creates AgentCore Gateway with MCP protocol
- Configures JWT authorization with Cognito
- Creates Lambda targets with tool schemas
- Manages gateway updates and deletions

### 2. Sample Tool Lambda

Located in `patterns/gateway/sample_tool_lambda.py`:

- Demonstrates proper Lambda target implementation
- Shows how to parse AgentCore Gateway event format
- Includes error handling and logging

### 3. IAM Roles and Permissions

**Gateway Role**: Allows gateway to invoke Lambda functions and access required AWS services

**Custom Resource Role**: Manages gateway lifecycle operations

### 4. SSM Parameter Storage

Gateway configuration is stored in SSM for easy access:

- `/stack-name/gateway_url`: Gateway endpoint URL
- `/stack-name/gateway_id`: Gateway identifier
- `/stack-name/target_id`: Lambda target identifier
- `/stack-name/machine_client_id`: Cognito client ID
- `/stack-name/machine_client_secret`: Cognito client secret

## Testing the Gateway

### Direct Gateway Testing

Use the provided test script to verify gateway functionality:

```bash
python3 scripts/test-gateway.py
```

This script:
1. Authenticates using machine client credentials
2. Lists available tools via `tools/list`
3. Calls the sample tool via `tools/call`
4. Displays responses for verification

### Integration with AgentCore Runtime

The gateway integrates with AgentCore Runtime through:

1. **Runtime Configuration**: Runtime is configured with gateway URL via SSM
2. **Authentication**: Runtime uses same Cognito user pool for JWT tokens
3. **Tool Discovery**: Runtime discovers tools via gateway's `tools/list` endpoint
4. **Tool Execution**: Runtime calls tools via gateway's `tools/call` endpoint

## Adding New Tools

To add a new tool to the gateway:

1. **Create Lambda Function**: Implement tool logic following the Lambda target pattern
2. **Define Tool Schema**: Add JSON schema definition to CDK stack
3. **Update Gateway Configuration**: Add new target to gateway custom resource
4. **Deploy**: Run CDK deploy to update infrastructure

### Example: Adding a Weather Tool

```typescript
// In backend-stack.ts
const weatherLambda = new lambda.Function(this, 'WeatherToolLambda', {
  runtime: lambda.Runtime.PYTHON_3_13,
  handler: 'weather_tool.handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../patterns/gateway')),
});

const weatherToolSchema = {
  "name": "get_weather",
  "description": "Get current weather for a location",
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City and state, e.g. 'Seattle, WA'"
      }
    },
    "required": ["location"]
  }
};
```

## Security Considerations

### Authentication
- Machine-to-machine authentication using Cognito client credentials
- JWT tokens with configurable expiration
- Scoped access using Cognito resource server

### Authorization
- Gateway validates JWT tokens on every request
- Lambda functions inherit gateway's IAM role permissions
- Principle of least privilege for all components

### Network Security
- Gateway endpoints use HTTPS only
- Lambda functions run in AWS managed VPC
- No direct internet access required for Lambda functions

## Monitoring and Logging

### CloudWatch Logs
- Gateway operations logged to `/aws/bedrock-agentcore/gateway/*`
- Lambda function logs in `/aws/lambda/function-name`
- Custom resource operations in `/aws/lambda/gateway-custom-resource`

### Metrics
- Gateway invocation metrics via CloudWatch
- Lambda function duration and error metrics
- Custom metrics can be added to Lambda functions

## Troubleshooting

### Common Issues

**"Unknown tool: None" Error**
- Indicates Lambda function isn't parsing context correctly
- Verify Lambda follows AgentCore Gateway input format
- Check CloudWatch logs for detailed error information

**Authentication Failures**
- Verify Cognito client credentials in SSM
- Check JWT token expiration
- Ensure gateway authorization configuration is correct

**Tool Not Found**
- Verify tool schema matches Lambda implementation
- Check gateway target configuration
- Ensure Lambda function is deployed and accessible

### Debug Steps

1. **Check SSM Parameters**: Verify all gateway configuration parameters exist
2. **Test Authentication**: Use test script to verify token generation
3. **Review CloudWatch Logs**: Check gateway and Lambda function logs
4. **Validate Tool Schema**: Ensure schema matches expected format
5. **Test Lambda Directly**: Invoke Lambda function independently to verify logic

## Best Practices

### Lambda Function Development
- Always log incoming events for debugging
- Implement proper error handling and return meaningful error messages
- Use environment variables for configuration
- Keep functions focused on single tool responsibility

### Schema Design
- Provide clear, descriptive tool and parameter descriptions
- Use appropriate JSON schema types and constraints
- Include examples in descriptions where helpful
- Keep input schemas simple and focused

### Deployment
- Test tools individually before gateway integration
- Use version tags for Lambda function deployments
- Monitor CloudWatch metrics after deployment
- Implement gradual rollout for production changes

## Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - How to deploy GASP infrastructure
- [Development Best Practices](../docs/development-best-practices.md) - General development guidelines
- [AWS AgentCore Gateway Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-gateway.html) - Official AWS documentation
