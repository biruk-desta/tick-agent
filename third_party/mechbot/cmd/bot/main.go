package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"mechbot/mech"
)

func main() {
	lines := make(chan []byte, 256)
	go func() {
		r := bufio.NewReaderSize(os.Stdin, 1<<20)
		for {
			line, err := r.ReadBytes('\n')
			if len(line) > 0 {
				lines <- line
			}
			if err != nil {
				close(lines)
				return
			}
		}
	}()
	out := bufio.NewWriterSize(os.Stdout, 1<<16)
	send := func(v any) {
		b, err := json.Marshal(v)
		if err != nil {
			return
		}
		out.Write(b)
		out.WriteByte('\n')
		out.Flush()
	}
	var brain *mech.Brain
	var probe struct {
		Type string `json:"type"`
	}
	for raw := range lines {
		probe.Type = ""
		if json.Unmarshal(raw, &probe) != nil {
			continue
		}
		switch probe.Type {
		case "hello":
			var h mech.Hello
			if err := json.Unmarshal(raw, &h); err != nil {
				fmt.Fprintln(os.Stderr, "hello:", err)
			}
			dir := h.Map.Dir
			if dir == "" {
				dir = "/arena"
			}
			w, err := mech.LoadWorld(dir)
			if err != nil {
				fmt.Fprintln(os.Stderr, "map:", err, "- playing on a flat map")
				w = mech.FlatWorld()
			}
			brain = mech.NewBrain(&h, w)
			send(map[string]string{"type": "ready"})
		case "obs":
			var o mech.Obs
			if err := json.Unmarshal(raw, &o); err != nil || brain == nil {
				var t struct {
					Tick int `json:"tick"`
				}
				json.Unmarshal(raw, &t)
				send(mech.Action{Tick: t.Tick})
				continue
			}
			send(brain.Act(&o))
		case "end":
			return
		}
	}
}
