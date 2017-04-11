package tools

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"

	"encoding/json"
	"github.com/g8os/go-client"
	ays "github.com/g8os/grid/api/ays-client"
	"github.com/garyburd/redigo/redis"
	"github.com/gorilla/mux"
	"github.com/patrickmn/go-cache"
)

const (
	connectionPoolMiddlewareKey         = "github.com/g8os/grid+connection-pool"
	connectionPoolMiddlewareDefaultPort = 6379
)

type ConnectionOptions func(*connectionMiddleware)

type API interface {
	ContainerCache() *cache.Cache
	AysAPIClient() *ays.AtYourServiceAPI
	AysRepoName() string
}

type redisInfo struct {
	RedisAddr     string
	RedisPort     int
	RedisPassword string
}

func ConnectionPortOption(port int) ConnectionOptions {
	return func(c *connectionMiddleware) {
		c.port = port
	}
}

func ConnectionPasswordOption(password string) ConnectionOptions {
	return func(c *connectionMiddleware) {
		c.password = password
	}
}

type connectionMiddleware struct {
	handler  http.Handler
	pools    *cache.Cache
	m        sync.Mutex
	port     int
	password string
}

func (c *connectionMiddleware) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	ctx := context.WithValue(r.Context(), connectionPoolMiddlewareKey, c)
	r = r.WithContext(ctx)

	c.handler.ServeHTTP(w, r)
}

func (c *connectionMiddleware) createPool(address, password string) *redis.Pool {
	pool := &redis.Pool{
		MaxIdle:     5,
		IdleTimeout: 5 * time.Minute,
		Dial: func() (redis.Conn, error) {
			// the redis protocol should probably be made sett-able
			c, err := redis.Dial("tcp", address)
			if err != nil {
				return nil, err
			}

			if len(password) > 0 {
				if _, err := c.Do("AUTH", password); err != nil {
					c.Close()
					return nil, err
				}
			} else {
				// check with PING
				if _, err := c.Do("PING"); err != nil {
					c.Close()
					return nil, err
				}
			}
			return c, err
		},
		// custom connection test method
		TestOnBorrow: func(c redis.Conn, t time.Time) error {
			if _, err := c.Do("PING"); err != nil {
				return err
			}
			return nil
		},
	}

	return pool
}

func (c *connectionMiddleware) getConnection(
	id string, api API) (client.Client, error) {
	c.m.Lock()
	defer c.m.Unlock()

	if pool, ok := c.pools.Get(id); ok {
		c.pools.Set(id, pool, cache.DefaultExpiration)
		return client.NewClientWithPool(pool.(*redis.Pool)), nil
	}

	srv, res, err := api.AysAPIClient().Ays.GetServiceByName(id, "node", api.AysRepoName(), nil, nil)

	if err != nil {
		return nil, err
	}

	if res.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Error getting service %v", id)
	}

	var info redisInfo
	if err := json.Unmarshal(srv.Data, &info); err != nil {
		return nil, err
	}

	pool := c.createPool(fmt.Sprintf("%s:%d", info.RedisAddr, int(info.RedisPort)), info.RedisPassword)

	c.pools.Set(id, pool, cache.DefaultExpiration)
	return client.NewClientWithPool(pool), nil
}

func (c *connectionMiddleware) onEvict(_ string, x interface{}) {
	x.(*redis.Pool).Close()
}

func ConnectionMiddleware(opt ...ConnectionOptions) func(h http.Handler) http.Handler {
	return func(h http.Handler) http.Handler {
		p := &connectionMiddleware{
			pools:   cache.New(5*time.Minute, 1*time.Minute),
			port:    connectionPoolMiddlewareDefaultPort,
			handler: h,
		}

		p.pools.OnEvicted(p.onEvict)
		for _, o := range opt {
			o(p)
		}

		return p
	}
}

func GetConnection(r *http.Request, api API) (client.Client, error) {
	p := r.Context().Value(connectionPoolMiddlewareKey)
	if p == nil {
		panic("middleware not injected")
	}

	vars := mux.Vars(r)
	id := vars["nodeid"]

	mw := p.(*connectionMiddleware)

	return mw.getConnection(id, api)
}

func GetContainerConnection(r *http.Request, api API) (client.Client, error) {
	nodeClient, err := GetConnection(r, api)
	if err != nil {
		return nil, err
	}

	id, err := GetContainerId(r, api)
	if err != nil {
		return nil, err
	}
	
	container := client.Container(nodeClient).Client(id)

	return container, nil
}

func GetContainerId(r *http.Request, api API) (int, error) {
	vars := mux.Vars(r)
	containerID := vars["containerid"]
	c := api.ContainerCache()
	var id int

	if cachedId, ok := c.Get(containerID); !ok {
		srv, res, err := api.AysAPIClient().Ays.GetServiceByName(containerID, "container", api.AysRepoName(), nil, nil)

		if err != nil {
			return id, err
		}

		if res.StatusCode != http.StatusOK {
			return id, fmt.Errorf("Error getting service %v", id)
		}

		var cID struct {
			Id int
		}

		if err := json.Unmarshal(srv.Data, &cID); err != nil {
			return id, err
		}
		id = cID.Id
	} else {
		id = cachedId.(int)
	}

	c.Set(containerID, id, cache.DefaultExpiration)
	return id, nil
}

func DeleteContainerId(r *http.Request, api API) {
	vars := mux.Vars(r)
	c := api.ContainerCache()
	c.Delete(vars["containerid"])
}