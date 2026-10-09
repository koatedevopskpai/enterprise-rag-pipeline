targetScope = 'resourceGroup'

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Name of the AI Services (Foundry) account.')
param accountName string

@description('Name of the Azure AI Search service (free tier).')
param searchName string

@description('Deployment environment (dev, test, prod).')
param environment string = 'dev'

@description('Owning team or individual.')
param owner string = 'koatedevopskpai'

@description('Cost center or budget owner.')
param costCenter string = 'personal'

@description('Project name used for cost reporting.')
param projectName string = 'enterprise-rag-pipeline'

@description('Date (yyyy-MM-dd) after which this resource set may be deleted.')
param expiresOn string = ''

var baseTags = {
  project: projectName
  environment: environment
  owner: owner
  costCenter: costCenter
  managedBy: 'bicep'
  workload: 'ai-103-portfolio'
  dataClassification: 'public'
}

var commonTags = empty(expiresOn) ? baseTags : union(baseTags, { expiresOn: expiresOn })

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  tags: commonTags
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
  }
}

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: location
  sku: {
    name: 'free'
  }
  tags: commonTags
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
  }
}

output openAiEndpoint string = account.properties.endpoint
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output accountName string = account.name
output searchName string = search.name
