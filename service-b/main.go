package main

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"
)

type Span struct {
	TraceID    string                 `json:"trace_id"`
	SpanID     string                 `json:"span_id"`
	ParentID   string                 `json:"parent_span_id,omitempty"`
	Name       string                 `json:"name"`
	Service    string                 `json:"service_name"`
	Kind       string                 `json:"kind"`
	StartTime  int64                  `json:"start_time_unix_nano"`
	EndTime    int64                  `json:"end_time_unix_nano"`
	Status     string                 `json:"status"`
	Attributes map[string]interface{} `json:"attributes"`
}

var (
	collectorURL = "http://trace-collector:4318/v1/traces"
	httpClient   = &http.Client{Timeout: 2 * time.Second}
)

func genID(n int) string {
	b := make([]byte, n)
	rand.Read(b)
	return hex.EncodeToString(b)
}

func sendSpan(s Span) {
	body, _ := json.Marshal(s)
	resp, err := httpClient.Post(collectorURL, "application/json", bytes.NewBuffer(body))
	if err != nil {
		log.Printf("failed to send span: %v", err)
		return
	}
	resp.Body.Close()
}

func handler(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/healthz" {
		w.WriteHeader(200)
		return
	}
	traceparent := r.Header.Get("traceparent")
	parts := strings.Split(traceparent, "-")
	traceID, parentID := "", ""
	if len(parts) >= 4 {
		traceID, parentID = parts[1], parts[2]
	}

	start := time.Now().UnixNano()
	time.Sleep(10 * time.Millisecond)
	end := time.Now().UnixNano()

	w.Write([]byte("done"))

	go sendSpan(Span{
		TraceID: traceID, SpanID: genID(8), ParentID: parentID,
		Name: "service-b-work", Service: "service-b", Kind: "SERVER",
		StartTime: start, EndTime: end, Status: "OK",
		Attributes: map[string]interface{}{"http.method": r.Method, "http.path": r.URL.Path},
	})
}

func main() {
	http.HandleFunc("/", handler)
	log.Println("Service B listening on :8082")
	log.Fatal(http.ListenAndServe(":8082", nil))
}