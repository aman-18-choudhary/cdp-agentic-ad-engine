output "namespace" {
  description = "Kubernetes namespace where CDP components are deployed"
  value       = var.namespace
}

output "redpanda_broker_url" {
  description = "Internal Redpanda/Kafka bootstrap broker URL"
  value       = "redpanda.${var.namespace}.svc.cluster.local:9093"
}

output "redpanda_admin_url" {
  description = "Redpanda admin API URL"
  value       = "http://redpanda.${var.namespace}.svc.cluster.local:9644"
}

output "redpanda_schema_registry_url" {
  description = "Redpanda Schema Registry URL"
  value       = "http://redpanda.${var.namespace}.svc.cluster.local:8081"
}

output "mongodb_uri" {
  description = "MongoDB connection URI with replica set"
  value       = "mongodb://mongodb-0.mongodb-headless.${var.namespace}.svc.cluster.local:27017/cdp?replicaSet=rs0"
  sensitive   = true
}

output "mongodb_host" {
  description = "MongoDB service hostname"
  value       = "mongodb.${var.namespace}.svc.cluster.local"
}

output "qdrant_grpc_url" {
  description = "Qdrant gRPC endpoint URL"
  value       = "qdrant.${var.namespace}.svc.cluster.local:6334"
}

output "qdrant_http_url" {
  description = "Qdrant HTTP endpoint URL"
  value       = "http://qdrant.${var.namespace}.svc.cluster.local:6333"
}

output "redis_url" {
  description = "Redis connection URL"
  value       = "redis://redis-master.${var.namespace}.svc.cluster.local:6379"
  sensitive   = true
}

output "minio_endpoint" {
  description = "MinIO S3-compatible endpoint URL"
  value       = "http://minio.${var.namespace}.svc.cluster.local:9000"
}

output "minio_console_url" {
  description = "MinIO web console URL"
  value       = "http://minio.${var.namespace}.svc.cluster.local:9001"
}

output "minio_access_key" {
  description = "MinIO root access key"
  value       = var.minio_root_user
  sensitive   = true
}

output "minio_secret_key" {
  description = "MinIO root secret key"
  value       = var.minio_root_password
  sensitive   = true
}
