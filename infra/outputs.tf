output "api_url" {
  description = "Base URL of the deployed ticket API."
  value       = "https://${azurerm_linux_web_app.api.default_hostname}"
}

output "api_docs_url" {
  description = "Interactive API documentation."
  value       = "https://${azurerm_linux_web_app.api.default_hostname}/docs"
}

output "resource_group_name" {
  description = "Resource group that contains all resources."
  value       = azurerm_resource_group.main.name
}