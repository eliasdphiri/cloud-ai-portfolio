#!/usr/bin/env python3
"""
AI-Powered Cloud Cost Optimizer
Author: Elias Dan Phiri
Description: Analyzes cloud spending patterns and provides AI-driven optimization recommendations
Technologies: Python, AWS SDK, Azure SDK, OpenAI API, Pandas
"""

import json
import pandas as pd
import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Any
import openai
from dataclasses import dataclass
import plotly.graph_objs as go
import plotly.io as pio

@dataclass
class CostAnalysis:
    """Data class for cost analysis results"""
    service: str
    current_cost: float
    projected_savings: float
    recommendations: List[str]
    priority: str

class CloudCostOptimizer:
    """
    AI-powered cloud cost optimization engine that analyzes spending patterns
    and provides actionable recommendations for cost reduction.
    """
    
    def __init__(self, aws_access_key: str, aws_secret_key: str, openai_api_key: str):
        """Initialize AWS and OpenAI clients"""
        self.ce_client = boto3.client(
            'ce',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name='us-east-1'
        )
        self.ec2_client = boto3.client(
            'ec2',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name='us-east-1'
        )
        self.cloudwatch = boto3.client(
            'cloudwatch',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name='us-east-1'
        )
        openai.api_key = openai_api_key
        
    def fetch_cost_data(self, days_back: int = 30) -> pd.DataFrame:
        """
        Fetch cost and usage data from AWS Cost Explorer
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            DataFrame with cost data by service
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        response = self.ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost', 'UsageQuantity'],
            GroupBy=[
                {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
            ]
        )
        
        # Parse response into DataFrame
        data = []
        for result in response['ResultsByTime']:
            date = result['TimePeriod']['Start']
            for group in result['Groups']:
                service = group['Keys'][0]
                usage_type = group['Keys'][1]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                usage = float(group['Metrics']['UsageQuantity']['Amount'])
                
                data.append({
                    'Date': date,
                    'Service': service,
                    'UsageType': usage_type,
                    'Cost': cost,
                    'Usage': usage
                })
        
        return pd.DataFrame(data)
    
    def analyze_ec2_utilization(self) -> Dict[str, Any]:
        """
        Analyze EC2 instance utilization to identify rightsizing opportunities
        
        Returns:
            Dictionary with underutilized instances and recommendations
        """
        instances = self.ec2_client.describe_instances()
        underutilized = []
        
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] != 'running':
                    continue
                
                instance_id = instance['InstanceId']
                instance_type = instance['InstanceType']
                
                # Get CPU utilization metrics
                cpu_stats = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=datetime.now() - timedelta(days=7),
                    EndTime=datetime.now(),
                    Period=3600,
                    Statistics=['Average', 'Maximum']
                )
                
                if cpu_stats['Datapoints']:
                    avg_cpu = sum(d['Average'] for d in cpu_stats['Datapoints']) / len(cpu_stats['Datapoints'])
                    max_cpu = max(d['Maximum'] for d in cpu_stats['Datapoints'])
                    
                    if avg_cpu < 20 and max_cpu < 50:
                        underutilized.append({
                            'InstanceId': instance_id,
                            'InstanceType': instance_type,
                            'AvgCPU': round(avg_cpu, 2),
                            'MaxCPU': round(max_cpu, 2),
                            'Recommendation': self._get_rightsizing_recommendation(instance_type, avg_cpu)
                        })
        
        return {
            'underutilized_instances': underutilized,
            'potential_savings': self._calculate_rightsizing_savings(underutilized)
        }
    
    def _get_rightsizing_recommendation(self, current_type: str, avg_cpu: float) -> str:
        """Generate rightsizing recommendation based on instance type and CPU usage"""
        size_map = {
            'xlarge': 'large',
            'large': 'medium',
            'medium': 'small',
            '2xlarge': 'xlarge',
            '4xlarge': '2xlarge'
        }
        
        for size, smaller in size_map.items():
            if size in current_type:
                recommended = current_type.replace(size, smaller)
                return f"Consider downsizing to {recommended} (Current CPU: {avg_cpu:.1f}%)"
        
        return f"Consider t3.micro or t3.small instances for this workload"
    
    def _calculate_rightsizing_savings(self, underutilized: List[Dict]) -> float:
        """Calculate potential savings from rightsizing"""
        # Simplified calculation - in production, use actual pricing API
        savings_per_instance = {
            'large': 50,
            'xlarge': 100,
            '2xlarge': 200,
            '4xlarge': 400
        }
        
        total_savings = 0
        for instance in underutilized:
            for size, saving in savings_per_instance.items():
                if size in instance['InstanceType']:
                    total_savings += saving * 30  # Monthly savings
                    break
        
        return total_savings
    
    def identify_unused_resources(self) -> Dict[str, List]:
        """
        Identify unused resources across AWS services
        
        Returns:
            Dictionary of unused resources by service
        """
        unused = {
            'ebs_volumes': [],
            'elastic_ips': [],
            'load_balancers': [],
            'rds_instances': []
        }
        
        # Check for unattached EBS volumes
        volumes = self.ec2_client.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )
        for volume in volumes['Volumes']:
            unused['ebs_volumes'].append({
                'VolumeId': volume['VolumeId'],
                'Size': volume['Size'],
                'Type': volume['VolumeType'],
                'MonthlyCoast': volume['Size'] * 0.10  # Simplified pricing
            })
        
        # Check for unassociated Elastic IPs
        addresses = self.ec2_client.describe_addresses()
        for address in addresses['Addresses']:
            if 'InstanceId' not in address:
                unused['elastic_ips'].append({
                    'AllocationId': address['AllocationId'],
                    'PublicIp': address['PublicIp'],
                    'MonthlyCost': 3.60  # $0.005 per hour
                })
        
        return unused
    
    def generate_ai_recommendations(self, cost_data: pd.DataFrame, 
                                   utilization_data: Dict) -> List[CostAnalysis]:
        """
        Use GPT to generate intelligent cost optimization recommendations
        
        Args:
            cost_data: DataFrame with cost information
            utilization_data: Dictionary with resource utilization metrics
            
        Returns:
            List of CostAnalysis objects with recommendations
        """
        # Prepare data summary for GPT
        cost_summary = cost_data.groupby('Service')['Cost'].sum().sort_values(ascending=False).head(10)
        
        prompt = f"""
        As a cloud cost optimization expert, analyze the following AWS spending data and provide 
        specific, actionable recommendations for cost reduction:
        
        Top 10 Services by Cost (Monthly):
        {cost_summary.to_string()}
        
        Underutilized Resources Found:
        - EC2 Instances with <20% CPU: {len(utilization_data.get('underutilized_instances', []))}
        - Unattached EBS Volumes: {len(utilization_data.get('ebs_volumes', []))}
        - Unassociated Elastic IPs: {len(utilization_data.get('elastic_ips', []))}
        
        Provide 5 specific recommendations with estimated savings percentages.
        Format as JSON with structure: 
        [{{"service": "name", "recommendation": "action", "estimated_savings": percentage}}]
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a cloud cost optimization expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        recommendations = json.loads(response.choices[0].message.content)
        
        # Convert to CostAnalysis objects
        analyses = []
        for rec in recommendations:
            service_cost = cost_summary.get(rec['service'], 0)
            analyses.append(CostAnalysis(
                service=rec['service'],
                current_cost=service_cost,
                projected_savings=service_cost * (rec['estimated_savings'] / 100),
                recommendations=[rec['recommendation']],
                priority='HIGH' if rec['estimated_savings'] > 20 else 'MEDIUM'
            ))
        
        return analyses
    
    def generate_cost_report(self, analyses: List[CostAnalysis], 
                           output_file: str = 'cost_optimization_report.html'):
        """
        Generate an interactive HTML report with cost optimization recommendations
        
        Args:
            analyses: List of cost analyses
            output_file: Output HTML file path
        """
        # Create visualizations
        services = [a.service for a in analyses]
        current_costs = [a.current_cost for a in analyses]
        savings = [a.projected_savings for a in analyses]
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(name='Current Cost', x=services, y=current_costs),
            go.Bar(name='Potential Savings', x=services, y=savings)
        ])
        
        fig.update_layout(
            title='Cloud Cost Optimization Opportunities',
            xaxis_title='Service',
            yaxis_title='Cost ($)',
            barmode='group'
        )
        
        # Generate HTML report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cloud Cost Optimization Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #2c5282; }}
                .metric {{ 
                    background: #f0f4f8; 
                    padding: 15px; 
                    border-radius: 8px; 
                    margin: 10px 0;
                }}
                .high {{ border-left: 4px solid #e53e3e; }}
                .medium {{ border-left: 4px solid #dd6b20; }}
                .savings {{ color: #38a169; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>AI-Powered Cloud Cost Optimization Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>Executive Summary</h2>
            <div class="metric">
                <h3>Total Potential Monthly Savings: <span class="savings">
                    ${sum(savings):,.2f}
                </span></h3>
                <p>Identified {len(analyses)} optimization opportunities across your cloud infrastructure.</p>
            </div>
            
            <h2>Cost Analysis Visualization</h2>
            {fig.to_html(include_plotlyjs='cdn')}
            
            <h2>Detailed Recommendations</h2>
        """
        
        for analysis in sorted(analyses, key=lambda x: x.projected_savings, reverse=True):
            priority_class = analysis.priority.lower()
            html_content += f"""
            <div class="metric {priority_class}">
                <h3>{analysis.service}</h3>
                <p><strong>Current Monthly Cost:</strong> ${analysis.current_cost:,.2f}</p>
                <p><strong>Potential Savings:</strong> <span class="savings">${analysis.projected_savings:,.2f}</span></p>
                <p><strong>Priority:</strong> {analysis.priority}</p>
                <p><strong>Recommendations:</strong></p>
                <ul>
                    {''.join(f'<li>{rec}</li>' for rec in analysis.recommendations)}
                </ul>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        return output_file

# Example usage and testing
if __name__ == "__main__":
    # Demo mode with sample data
    print("Cloud Cost Optimizer - Portfolio Demo")
    print("=" * 50)
    
    # Create sample data for demonstration
    sample_analyses = [
        CostAnalysis(
            service="Amazon EC2",
            current_cost=2500.00,
            projected_savings=875.00,
            recommendations=[
                "Implement auto-scaling to reduce idle capacity during off-peak hours",
                "Convert 40% of on-demand instances to Reserved Instances",
                "Rightsize m5.2xlarge instances to m5.xlarge based on CPU utilization"
            ],
            priority="HIGH"
        ),
        CostAnalysis(
            service="Amazon RDS",
            current_cost=1800.00,
            projected_savings=450.00,
            recommendations=[
                "Enable storage auto-scaling to prevent over-provisioning",
                "Switch development databases to Aurora Serverless v2",
                "Implement automated snapshot lifecycle policies"
            ],
            priority="HIGH"
        ),
        CostAnalysis(
            service="Amazon S3",
            current_cost=800.00,
            projected_savings=240.00,
            recommendations=[
                "Move infrequently accessed data to S3 Glacier",
                "Implement S3 Intelligent-Tiering for automatic cost optimization",
                "Delete orphaned multipart uploads and old versions"
            ],
            priority="MEDIUM"
        )
    ]
    
    print(f"✓ Analyzed {len(sample_analyses)} AWS services")
    print(f"✓ Total monthly cost: ${sum(a.current_cost for a in sample_analyses):,.2f}")
    print(f"✓ Potential savings: ${sum(a.projected_savings for a in sample_analyses):,.2f}")
    print(f"✓ ROI: {(sum(a.projected_savings for a in sample_analyses) / sum(a.current_cost for a in sample_analyses)) * 100:.1f}%")
    print("\nTop Recommendation: " + sample_analyses[0].recommendations[0])
