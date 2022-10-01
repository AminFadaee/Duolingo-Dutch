package main

import (
	"fmt"
	"github.com/gocolly/colly"
	"strings"
)

type word struct{ Dutch, Translation, Tag string }

func main() {
	words := make([]word, 0, 1000)
	query := "//div[@class=\"hlist\"]/a/@href"
	link := "https://duolingo.fandom.com/wiki/Dutch_(Netherlands)"
	tags := make([]string, 0, 100)
	c := colly.NewCollector(
		colly.UserAgent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11"),
	)
	c.OnError(func(r *colly.Response, err error) {
		fmt.Println("Request URL:", r.Request.URL, "failed with response:", string(r.Body), "\nError:", err)
	})
	c.OnXML(query, func(e *colly.XMLElement) {
		tag := strings.SplitN(e.Text, ":", 2)[1]
		tags = append(tags, tag)
	})
	c.Visit(link)
	for _, tag := range tags {
		words = append(words, crawl(tag)...)
	}
	for _, word := range words {
		fmt.Printf("%s$$$%s$$$%s\n", word.Dutch, word.Translation, word.Tag)
	}
}

func crawl(tag string) []word {
	link := fmt.Sprintf("https://duolingo.fandom.com/wiki/Dutch_(NL)_Skill:%s", tag)
	query := "//ul/li"
	c := colly.NewCollector(
		colly.UserAgent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11"),
	)
	c.OnError(func(r *colly.Response, err error) {
		fmt.Println("Request URL:", r.Request.URL, "failed with response:", string(r.Body), "\nError:", err)
	})
	words := make([]word, 0, 5)
	c.OnXML(query, func(e *colly.XMLElement) {
		if strings.Contains(e.Text, "=") {
			splits := strings.SplitN(e.Text, "=", 2)
			words = append(words, word{strings.TrimSpace(splits[0]), strings.TrimSpace(splits[1]), tag})

		}
	})
	c.Visit(link)
	return words
}
