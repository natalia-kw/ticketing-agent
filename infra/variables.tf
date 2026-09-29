variable "app_name" {
  description = "Base name for all resources. The web app name must be globally unique in Azure."
  type        = string
  default     = "ticketing-api"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$", var.app_name))
    error_message = "app_name must be 3 to 40 lowercase letters, numbers or hyphens, and start and end with a letter or number."
  }
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "swedencentral"
}

variable "sku_name" {
  description = "App Service plan size, for example B1 (basic) or P1v3 (production)."
  type        = string
  default     = "B1"
}

variable "subscription_id" {
  description = "Azure subscription to deploy into. Required for plan and apply, not for validate."
  type        = string
}