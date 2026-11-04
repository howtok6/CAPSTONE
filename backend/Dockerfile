# Backend Go de la app «Vía». Binario estático sobre una imagen mínima.
FROM golang:1.25-alpine AS compilacion
WORKDIR /src
COPY go.mod ./
COPY . .
ARG VERSION=dev
RUN CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -X main.version=${VERSION}" \
    -o /via-backend ./cmd/via-backend

# distroless/static incluye los certificados raíz para hablar HTTPS con OSRM y Nominatim.
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=compilacion /via-backend /via-backend
ENV VIA_DIRECCION=:8080
EXPOSE 8080
USER nonroot
ENTRYPOINT ["/via-backend"]
