terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

locals {
  tags = {
    project    = var.app_name
    managed_by = "terraform"
  }
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.app_name}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_service_plan" "main" {
  name                = "asp-${var.app_name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = var.sku_name
  tags                = local.tags
}

resource "azurerm_linux_web_app" "api" {
  name                = "app-${var.app_name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true
  tags                = local.tags

  site_config {
    app_command_line                  = "uvicorn api.main:app --host 0.0.0.0 --port 8000"
    health_check_path                 = "/health"
    health_check_eviction_time_in_min = 5

    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = {
    SEED_DATA                      = "true"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
  }
}