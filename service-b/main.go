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
	TraceID   string `json:"trace_id"`
	SpanID    string `json:"span_id"`
	ParentID  string `json:"parent_span_id"`
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
	http.Post("http://trace-collector:4318/v1/traces", "application/json", bytes.NewBuffer(body))
}

func handler(w http.ResponseWriter, r *http.Request) {
	traceparent := r.Header.Get("traceparent")
	parts := strings.Split(traceparent, "-")
	traceID, parentID := "", ""
	if len(parts) >= 4 {
		traceID = parts[1]
		parentID = parts[2]
	}

	start := time.Now().UnixNano()
	time.Sleep(10 * time.Millisecond)
	end := time.Now().UnixNano()

	spanID := genID(8)
	sendSpan(Span{
		TraceID: traceID, SpanID: spanID, ParentID: parentID,
		Name: "service-b-work", Service: "service-b",
		StartTime: start, EndTime: end,
	})

	w.Write([]byte("done"))
}

func main() {
	http.HandleFunc("/work", handler)
	log.Println("Service B listening on :8082")
	log.Fatal(http.ListenAndServe(":8082", nil))
}
