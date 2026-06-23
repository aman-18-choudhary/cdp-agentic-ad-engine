variable "kubeconfig_path" {
  description = "Path to the kubeconfig file for K3s cluster access"
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Kubernetes context to use (leave empty for default)"
  type        = string
  default     = ""
}

variable "namespace" {
  description = "Kubernetes namespace for all CDP components"
  type        = string
  default     = "cdp"
}

variable "storage_class" {
  description = "Storage class for persistent volumes"
  type        = string
  default     = "local-path"
}

# ── Redpanda ──

variable "redpanda_replicas" {
  description = "Number of Redpanda broker replicas"
  type        = number
  default     = 1
}

# ── MongoDB ──

variable "mongodb_replicas" {
  description = "Number of MongoDB replica set members (minimum 3 for production)"
  type        = number
  default     = 1
}

# ── Qdrant ──

variable "qdrant_replicas" {
  description = "Number of Qdrant node replicas"
  type        = number
  default     = 1
}

# ── MinIO ──

variable "minio_root_user" {
  description = "MinIO root user (access key)"
  type        = string
  sensitive   = true
  default     = "cdpadmin"
}

variable "minio_root_password" {
  description = "MinIO root user password (secret key)"
  type        = string
  sensitive   = true
  default     = "cdpadmin123"
}

# ── Redis ──

variable "redis_replicas" {
  description = "Number of Redis replicas"
  type        = number
  default     = 1
}
