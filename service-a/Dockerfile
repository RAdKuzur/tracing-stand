FROM golang:1.27.0-alpine AS builder
WORKDIR /app
COPY go.mod ./
COPY main.go ./
RUN go build -o service .

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/service .
EXPOSE 8081 8082
CMD ["./service"]