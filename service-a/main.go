package main

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"
)

type Span struct {
	TraceID   string `json:"trace_id"`
	SpanID    string `json:"span_id"`
	Name      string `json:"name"`
	Service   string `json:"service_name"`
	StartTime int64  `json:"start_time_unix_nano"`
	EndTime   int64  `json:"end_time_unix_nano"`
}

func genID(n int) string {
	b := make([]byte, n)
	rand.Read(b)
	return hex.EncodeToString(b)
}

func sendSpan(s Span) {
	body, _ := json.Marshal(s)
	resp, err := http.Post("http://trace-collector:4318/v1/traces", "application/json", bytes.NewBuffer(body))
	if err != nil {
		log.Printf("failed to send span: %v", err)
		return
	}
	defer resp.Body.Close()
}

func handler(w http.ResponseWriter, r *http.Request) {
	traceID := genID(16)
	spanID := genID(8)
	start := time.Now().UnixNano()

	req, _ := http.NewRequest("GET", "http://service-b:8082/work", nil)
	req.Header.Set("traceparent", fmt.Sprintf("00-%s-%s-01", traceID, spanID))
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Do(req)
	if err == nil {
		resp.Body.Close()
	}

	end := time.Now().UnixNano()
	sendSpan(Span{
		TraceID: traceID, SpanID: spanID, Name: "service-a-handler",
		Service: "service-a", StartTime: start, EndTime: end,
	})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"trace_id": traceID, "status": "ok"})
}

func main() {
	http.HandleFunc("/", handler)
	log.Println("Service A listening on :8081")
	log.Fatal(http.ListenAndServe(":8081", nil))
}
