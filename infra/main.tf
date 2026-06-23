terraform {
  required_version = ">= 1.5.0"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
  }
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
    config_context = var.kube_context
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
  config_context = var.kube_context
}

# ──────────────────────────────────────────────
# Namespace
# ──────────────────────────────────────────────

resource "kubernetes_namespace" "cdp" {
  metadata {
    name = var.namespace
    labels = {
      app = "cdp"
      managed_by = "terraform"
    }
  }
}

# ──────────────────────────────────────────────
# Redpanda (Kafka-compatible message broker)
# ──────────────────────────────────────────────

resource "helm_release" "redpanda" {
  name       = "redpanda"
  repository = "https://charts.redpanda.com"
  chart      = "redpanda"
  version    = "5.7.3"
  namespace  = var.namespace
  depends_on = [kubernetes_namespace.cdp]

  values = [
    yamlencode({
      statefulset = {
        replicas = var.redpanda_replicas
      }
      resources = {
        requests = {
          cpu    = "250m"
          memory = "512Mi"
        }
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      storage = {
        persistentVolume = {
          enabled      = true
          storageClass = var.storage_class
          size         = "10Gi"
        }
      }
      listeners = {
        kafka = {
          port = 9093
          external = {
            enabled = false
          }
        }
        admin = {
          enabled = true
          port    = 9644
        }
      }
    })
  ]
}

# ──────────────────────────────────────────────
# MongoDB (Replica Set for Change Streams)
# ──────────────────────────────────────────────

resource "helm_release" "mongodb" {
  name       = "mongodb"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "mongodb"
  version    = "15.1.0"
  namespace  = var.namespace
  depends_on = [kubernetes_namespace.cdp]

  values = [
    yamlencode({
      architecture = "replicaset"
      replicaCount = var.mongodb_replicas
      auth = {
        enabled = false
      }
      replicaSetName = "rs0"
      persistence = {
        enabled      = true
        storageClass = var.storage_class
        size         = "5Gi"
      }
      resources = {
        requests = {
          cpu    = "200m"
          memory = "256Mi"
        }
        limits = {
          cpu    = "500m"
          memory = "1Gi"
        }
      }
      metrics = {
        enabled = false
      }
    })
  ]
}

# ──────────────────────────────────────────────
# Qdrant (Vector Database)
# ──────────────────────────────────────────────

resource "helm_release" "qdrant" {
  name       = "qdrant"
  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  version    = "1.0.3"
  namespace  = var.namespace
  depends_on = [kubernetes_namespace.cdp]

  values = [
    yamlencode({
      replicaCount = var.qdrant_replicas
      persistence = {
        enabled      = true
        storageClass = var.storage_class
        size         = "5Gi"
      }
      resources = {
        requests = {
          cpu    = "100m"
          memory = "256Mi"
        }
        limits = {
          cpu    = "500m"
          memory = "512Mi"
        }
      }
      grpc = {
        enabled = true
        port    = 6334
      }
    })
  ]
}

# ──────────────────────────────────────────────
# Redis (Caching)
# ──────────────────────────────────────────────

resource "helm_release" "redis" {
  name       = "redis"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "redis"
  version    = "19.1.5"
  namespace  = var.namespace
  depends_on = [kubernetes_namespace.cdp]

  values = [
    yamlencode({
      architecture = "standalone"
      master = {
        count = 1
        persistence = {
          enabled      = true
          storageClass = var.storage_class
          size         = "1Gi"
        }
        resources = {
          requests = {
            cpu    = "100m"
            memory = "64Mi"
          }
          limits = {
            cpu    = "250m"
            memory = "256Mi"
          }
        }
      }
      auth = {
        enabled = false
      }
    })
  ]
}

# ──────────────────────────────────────────────
# MinIO (S3-compatible Object Store)
# ──────────────────────────────────────────────

resource "helm_release" "minio" {
  name       = "minio"
  repository = "https://charts.min.io"
  chart      = "minio"
  version    = "5.4.0"
  namespace  = var.namespace
  depends_on = [kubernetes_namespace.cdp]

  values = [
    yamlencode({
      mode = "standalone"
      replicas = 1
      persistence = {
        enabled      = true
        storageClass = var.storage_class
        size         = "10Gi"
      }
      resources = {
        requests = {
          cpu    = "100m"
          memory = "128Mi"
        }
        limits = {
          cpu    = "500m"
          memory = "512Mi"
        }
      }
      rootUser     = var.minio_root_user
      rootPassword = var.minio_root_password
      buckets = [
        {
          name   = "raw-events"
          policy = "none"
          purge  = false
        }
      ]
    })
  ]
}

# ──────────────────────────────────────────────
# KEDA (Event-driven Autoscaler)
# ──────────────────────────────────────────────

resource "helm_release" "keda" {
  name       = "keda"
  repository = "https://kedacore.github.io/charts"
  chart      = "keda"
  version    = "2.14.0"
  namespace  = var.namespace
  depends_on = [kubernetes_namespace.cdp]

  values = [
    yamlencode({
      replicaCount = 1
      resources = {
        requests = {
          cpu    = "100m"
          memory = "128Mi"
        }
        limits = {
          cpu    = "500m"
          memory = "256Mi"
        }
      }
      operator = {
        logLevel = "info"
      }
      webhooks = {
        enabled = false
      }
    })
  ]
}
