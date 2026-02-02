

# 🚀 Guía práctica: Docker → Kubernetes (Comandos + Flujo real)

Este README es un **cheat sheet listo para copiar** con los comandos más útiles de **Docker, Docker Compose y Kubernetes**, más un **paso a paso para migrar de Docker a Kubernetes**.

Está pensado para proyectos de microservicios y aprendizaje práctico.

---

# ✅ Requisitos previos

Tener instalado:

- Docker Desktop  
- Docker Compose v2  
- kubectl  
- minikube **o** kind (para Kubernetes local)

Verificar instalación:

```bash
docker --version
docker compose version
kubectl version --client
minikube version   # opcional
kind version       # opcional


---

===========================

🐳 1) DOCKER (BÁSICO A PRO)

===========================

1.1 Información general

docker info
docker ps
docker ps -a
docker images


---

1.2 Construir imágenes

Desde un Dockerfile:

docker build -t myapp:1.0 .
docker build -t myapp:latest .

Sin caché (útil cuando cambias dependencias):

docker build --no-cache -t myapp:latest .


---

1.3 Ejecutar contenedores

Básico:

docker run --name myapp -p 8000:8000 myapp:latest

En segundo plano:

docker run -d --name myapp -p 8000:8000 myapp:latest

Con variables de entorno:

docker run -d --name myapp -p 8000:8000 \
  -e ENV=prod \
  -e PORT=8000 \
  myapp:latest

Montar carpeta local dentro del contenedor:

docker run -d --name myapp -p 8000:8000 \
  -v "$(pwd)":/app \
  myapp:latest


---

1.4 Logs y acceso al contenedor

docker logs -f myapp
docker exec -it myapp bash
docker exec -it myapp sh


---

1.5 Detener y borrar

docker stop myapp
docker rm myapp
docker rm -f myapp


---

1.6 Redes y volúmenes

docker network ls
docker network create mynet
docker volume ls
docker volume create pgdata

Limpiar todo lo no usado:

docker system prune -f
docker volume prune -f


---

=================================

🐙 2) DOCKER COMPOSE (RECOMENDADO)

=================================

Levantar todo:

docker compose up
docker compose up -d
docker compose up -d --build

Ver estado:

docker compose ps
docker compose logs -f
docker compose logs -f gateway

Reiniciar un servicio:

docker compose restart gateway

Bajar todo:

docker compose down
docker compose down -v   # borra volúmenes

Entrar a un servicio:

docker compose exec gateway bash


---

===================================

📦 3) DOCKER HUB (SUBIR IMÁGENES)

===================================

Login:

docker login

Taggear imagen:

docker tag myapp:latest tuusuario/myapp:latest

Subir a Docker Hub:

docker push tuusuario/myapp:latest

Bajar imagen:

docker pull tuusuario/myapp:latest


---

===================================

☸️ 4) KUBERNETES (kubectl)

===================================

4.1 Contexto y cluster

kubectl cluster-info
kubectl config get-contexts
kubectl config use-context minikube


---

4.2 Namespaces

kubectl get ns
kubectl create ns dev
kubectl config set-context --current --namespace=dev


---

4.3 Aplicar archivos YAML

kubectl apply -f k8s/
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml


---

4.4 Ver recursos

kubectl get pods
kubectl get deploy
kubectl get svc
kubectl get ingress
kubectl get events --sort-by=.metadata.creationTimestamp


---

4.5 Debug y logs

kubectl describe pod myapp-xyz
kubectl logs myapp-xyz
kubectl logs -f myapp-xyz

Entrar al pod:

kubectl exec -it myapp-xyz -- bash


---

4.6 Escalar replicas

kubectl scale deployment/myapp --replicas=3
kubectl get pods -w


---

4.7 Rollout (versiones)

kubectl rollout status deployment/myapp
kubectl rollout history deployment/myapp
kubectl rollout undo deployment/myapp


---

4.8 Port-forward (probar local)

kubectl port-forward svc/myapp-service 8080:80

Luego abres:

http://localhost:8080


---

=========================================

🔁 5) CÓMO PASAR DE DOCKER A KUBERNETES

=========================================

👉 Paso 1 — Lo que ya tienes en Docker

Supón que tienes esto funcionando con Docker Compose:

docker compose up -d

Y tu app corre en:

http://localhost:8000


---

👉 Paso 2 — Construyes tu imagen final

docker build -t tuusuario/myapp:latest .
docker push tuusuario/myapp:latest


---

👉 Paso 3 — Creas tu Deployment (K8s)

Archivo: k8s/deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: myapp
          image: tuusuario/myapp:latest
          ports:
            - containerPort: 8000


---

👉 Paso 4 — Creas el Service

Archivo: k8s/service.yaml

apiVersion: v1
kind: Service
metadata:
  name: myapp-service
spec:
  selector:
    app: myapp
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: NodePort


---

👉 Paso 5 — Levantas Kubernetes local

Con Minikube:

minikube start


---

👉 Paso 6 — Aplicar a Kubernetes

kubectl apply -f k8s/
kubectl get pods
kubectl get svc


---

👉 Paso 7 — Probar tu app

kubectl port-forward svc/myapp-service 8080:80

Y abres:

http://localhost:8080

🎉 ¡Tu app ya está en Kubernetes!


---

=========================================

🧠 6) FLUJO REAL (RECOMENDADO)

=========================================

🔹 Desarrollo local (Docker)

docker compose up -d --build

🔹 Subir imagen a Docker Hub

docker build -t tuusuario/myapp:latest .
docker push tuusuario/myapp:latest

🔹 Desplegar en Kubernetes

kubectl apply -f k8s/
kubectl get pods -w

🔹 Ver logs

kubectl logs -f deployment/myapp


---

=========================================

🐞 7) ERRORES COMUNES Y SOLUCIONES

=========================================

❌ CrashLoopBackOff

kubectl describe pod myapp-xyz
kubectl logs myapp-xyz --previous

❌ ImagePullBackOff

Verifica que el nombre sea correcto:


tusuario/myapp:latest

Verifica que hiciste docker push



---

✅ RESUMEN FINAL

Etapa	Herramienta

Desarrollo	Docker
Orquestación local	Docker Compose
Producción	Kubernetes
Registro	Docker Hub



---
