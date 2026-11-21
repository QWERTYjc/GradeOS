// Optional local optical hints. No network, no rubric, no grading decisions.
import Foundation
import Vision
import CryptoKit

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let documents = try JSONSerialization.jsonObject(with: Data(contentsOf: inputURL)) as! [String: [String: Any]]
var results: [String: Any] = [:]
for (id, document) in documents {
    var pages: [[String: Any]] = []
    for page in document["pages"] as! [[String: Any]] {
        let url = URL(fileURLWithPath: page["absolute_path"] as! String)
        let data = try Data(contentsOf: url)
        let hash = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard hash == page["sha256"] as! String else { fatalError("Source changed before optical observation") }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["en-US"]
        do {
            try VNImageRequestHandler(data: data, options: [:]).perform([request])
        } catch let error as NSError {
            // The verified source image is still usable when Vision cannot run on this machine.
            pages.append(["page": page["page"]!, "source_sha256": hash, "rows": [],
                          "status": "unavailable", "error_domain": error.domain, "error_code": error.code])
            continue
        }
        let rows = (request.results ?? []).map { observation -> [String: Any] in
            let box = observation.boundingBox
            return ["rect": [Double(box.minX), Double(1-box.maxY), Double(box.width), Double(box.height)],
                    "candidates": observation.topCandidates(2).map { ["text": $0.string, "confidence": $0.confidence] }]
        }.sorted { left, right in
            let a=left["rect"] as! [Double], b=right["rect"] as! [Double]
            let bandA=Int(floor(a[1]/0.008)), bandB=Int(floor(b[1]/0.008))
            if bandA != bandB { return bandA < bandB }
            return a[0] == b[0] ? a[1] < b[1] : a[0] < b[0]
        }
        pages.append(["page": page["page"]!, "source_sha256": hash, "rows": rows])
    }
    results[id] = ["source_sha256": document["sha256"]!, "pages": pages]
}
let output: [String: Any] = ["version": 1, "engine": "Apple Vision VNRecognizeTextRequest",
    "network_requests": 0, "language_correction": false, "documents": results]
try JSONSerialization.data(withJSONObject: output, options: [.prettyPrinted, .sortedKeys]).write(to: outputURL, options: .withoutOverwriting)
