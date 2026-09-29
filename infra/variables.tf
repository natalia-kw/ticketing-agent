variable "app_name" {
  description = "Base name for all resources. The web app name must be globally unique in Azure."
  type        = string
  default     = "ticketing-api"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,40}$", var.app_name))
    error_message = "app_name may only contain lowercase letters, numbers and hyphens (3 to 40 characters)."
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
  description = "Azure subscription to deploy into. Placeholder, replace before deploying."
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}