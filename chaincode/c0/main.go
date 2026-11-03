package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/hyperledger/fabric-chaincode-go/v2/pkg/cid"
	"github.com/hyperledger/fabric-chaincode-go/v2/shim"
	pb "github.com/hyperledger/fabric-protos-go-apiv2/peer"
)

const farmCollection = "pdc_farm_integrator"

// Public fields only. Adding a sensitive field is rejected by strictJSON.
type Batch struct {
	BatchID    string `json:"batchId"`
	FarmID     string `json:"farmId"`
	HatcheryID string `json:"hatcheryId"`
	Population int    `json:"population"`
	Status     string `json:"status"`
}

type FarmPerformance struct {
	BatchID           string  `json:"batchId"`
	FCR               float64 `json:"fcr"`
	MortalityRate     float64 `json:"mortalityRate"`
	ProductionCostIDR int64   `json:"productionCostIdr"`
}

type PoultryTrace struct{}

func (c *PoultryTrace) Init(stub shim.ChaincodeStubInterface) *pb.Response {
	return shim.Success(nil)
}

func (c *PoultryTrace) Invoke(stub shim.ChaincodeStubInterface) *pb.Response {
	fn, args := stub.GetFunctionAndParameters()
	var data []byte
	var err error
	switch fn {
	case "CreateBatch":
		err = createBatch(stub, args)
	case "GetBatch":
		data, err = getBatch(stub, args)
	case "RecordFarmPerformance":
		err = recordPerformance(stub, args, false)
	case "ReadFarmPerformance":
		data, err = readPerformance(stub, args)
	case "UpdateFarmPerformance":
		err = recordPerformance(stub, args, true)
	default:
		return shim.Error("unknown function")
	}
	if err != nil {
		return shim.Error(err.Error())
	}
	return shim.Success(data)
}

func strictJSON(raw []byte, dst interface{}) error {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		return errors.New("invalid JSON schema")
	}
	if err := dec.Decode(new(interface{})); err != io.EOF {
		return errors.New("unexpected trailing JSON")
	}
	return nil
}

func requiresOrg(stub shim.ChaincodeStubInterface, allowed ...string) error {
	org, err := cid.GetMSPID(stub)
	if err != nil {
		return errors.New("cannot verify caller organization")
	}
	for _, a := range allowed {
		if org == a {
			return nil
		}
	}
	return errors.New("access denied")
}

func validBatchID(id string) bool {
	if len(id) < 3 || len(id) > 64 {
		return false
	}
	for _, ch := range id {
		if !((ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '-') {
			return false
		}
	}
	return true
}

func createBatch(stub shim.ChaincodeStubInterface, args []string) error {
	if err := requiresOrg(stub, "FarmOrgMSP", "IntegratorOrgMSP", "HatcheryOrgMSP"); err != nil {
		return err
	}
	if len(args) != 1 {
		return errors.New("CreateBatch requires one public JSON argument")
	}
	var batch Batch
	if err := strictJSON([]byte(args[0]), &batch); err != nil {
		return err
	}
	if !validBatchID(batch.BatchID) || strings.TrimSpace(batch.FarmID) == "" || batch.Population <= 0 || batch.Status == "" {
		return errors.New("invalid public batch fields")
	}
	key := "batch:" + batch.BatchID
	existing, err := stub.GetState(key)
	if err != nil {
		return errors.New("cannot read batch")
	}
	if existing != nil {
		return errors.New("batch already exists")
	}
	b, err := json.Marshal(batch)
	if err != nil {
		return errors.New("cannot encode batch")
	}
	if err = stub.PutState(key, b); err != nil {
		return errors.New("cannot write batch")
	}
	return nil // Never return private or batch content in the write response.
}

func getBatch(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 || !validBatchID(args[0]) {
		return nil, errors.New("invalid batch ID")
	}
	b, err := stub.GetState("batch:" + args[0])
	if err != nil {
		return nil, errors.New("cannot read batch")
	}
	if b == nil {
		return nil, errors.New("batch not found")
	}
	return b, nil
}

func performanceKey(id string) string { return "performance:" + id }

func recordPerformance(stub shim.ChaincodeStubInterface, args []string, update bool) error {
	if err := requiresOrg(stub, "FarmOrgMSP"); err != nil {
		return err
	}
	if len(args) != 1 || !validBatchID(args[0]) {
		return errors.New("invalid batch ID")
	}
	batchID := args[0]
	pub, err := stub.GetState("batch:" + batchID)
	if err != nil || pub == nil {
		return errors.New("public batch not found")
	}
	trans, err := stub.GetTransient()
	if err != nil {
		return errors.New("transient data unavailable")
	}
	raw := trans["performance"]
	if len(raw) == 0 || len(raw) > 8192 {
		return errors.New("performance transient missing or too large")
	}
	var p FarmPerformance
	if err = strictJSON(raw, &p); err != nil {
		return err
	}
	if p.BatchID != batchID || p.FCR <= 0 || p.FCR > 5 || p.MortalityRate < 0 || p.MortalityRate > 100 || p.ProductionCostIDR < 0 {
		return errors.New("invalid performance fields")
	}
	key := performanceKey(batchID)
	previous, err := stub.GetPrivateData(farmCollection, key)
	if err != nil {
		return errors.New("cannot verify private record")
	}
	if update && previous == nil {
		return errors.New("private record does not exist")
	}
	if !update && previous != nil {
		return errors.New("private record already exists")
	}
	b, err := json.Marshal(p)
	if err != nil {
		return errors.New("cannot encode performance")
	}
	if err = stub.PutPrivateData(farmCollection, key, b); err != nil {
		return errors.New("cannot save private record")
	}
	return nil // Private data must never be present in proposal response payload.
}

func readPerformance(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if err := requiresOrg(stub, "FarmOrgMSP", "IntegratorOrgMSP"); err != nil {
		return nil, err
	}
	if len(args) != 1 || !validBatchID(args[0]) {
		return nil, errors.New("invalid batch ID")
	}
	b, err := stub.GetPrivateData(farmCollection, performanceKey(args[0]))
	if err != nil {
		return nil, errors.New("private record unavailable")
	}
	if b == nil {
		return nil, errors.New("private record not found")
	}
	return b, nil // Evaluate/query only for authorized caller, not a write proposal.
}

func main() {
	ccid := os.Getenv("CHAINCODE_ID")
	if ccid == "" {
		panic("CHAINCODE_ID is required")
	}
	address := os.Getenv("CHAINCODE_SERVER_ADDRESS")
	if address == "" {
		address = "127.0.0.1:9999"
	}
	srv := &shim.ChaincodeServer{
		CCID:     ccid,
		Address:  address,
		CC:       &PoultryTrace{},
		TLSProps: shim.TLSProperties{Disabled: true}, // loopback ONLY in each Coder machine
	}
	if err := srv.Start(); err != nil {
		panic(fmt.Errorf("chaincode service stopped: %w", err))
	}
}
